import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

from PIL import Image

import app
from territories import (ASSESSMENT_FIELDS,PROFILES,NORFOLK_BUILDING_CONTEXT,assessment_address,assessment_choice,
                         canonical_address,get_profile,norfolk_address_where,norfolk_land_use,numeric_id)


def assessment(use,description,**kwargs):
    return dict(property_use=use,property_class_description=description,**kwargs)


def site_for(row,size=3000):
    return {'land':norfolk_land_use(row),'zone':'','facility':'','facility_kind':'','fcodes':[],
            'largest':size,'avg':size,'count':1,'buildings':[]}


def square(lon=-76.28,lat=36.85,side=100):
    return [app.lonlat_offset(lon,lat,dx,dy) for dx,dy in
            ((-side/2,-side/2),(side/2,-side/2),(side/2,side/2),(-side/2,side/2),(-side/2,-side/2))]


class TerritoryNormalizationTests(unittest.TestCase):
    def test_profiles_use_separate_city_sources(self):
        vb,nf=get_profile(),get_profile('norfolk')
        for field in ('address','parcel','building','imagery'):
            self.assertNotEqual(vb[field],nf[field])
        self.assertEqual(nf['imagery_kind'],'map_server')
        self.assertEqual(vb['imagery_kind'],'image_server')
        self.assertIn('/AerialPhotos/2025/MapServer/export',nf['imagery'])
        self.assertNotIn('norfolk',vb['imagery'])
        self.assertIn('qva7-tzrf',nf['assessment'])

    def test_unknown_territory_never_silently_uses_vb(self):
        with self.assertRaisesRegex(ValueError,'Unsupported territory'):get_profile('chesapeake')
        with self.assertRaises(ValueError):app.image_request_params(-76.28,36.85,800,territory='unknown')

    def test_numeric_gpin_join_does_not_round_or_accept_sql(self):
        for value in (1437152565,'1437152565','1437152565.0',' 1437152565 '):
            self.assertEqual(numeric_id(value),'1437152565')
        for value in (None,'','1437152565.1',"1) OR 1=1",'abc'):
            self.assertEqual(numeric_id(value),'')

    def test_address_abbreviations_and_direction(self):
        self.assertEqual(canonical_address('800 East City Hall Avenue, Norfolk, VA 23510'),'800 E CITY HALL AVE')
        self.assertEqual(norfolk_address_where('800 E City Hall Ave'),"HSE_NUM = 800 AND UPPER(ST_NAME) = 'CITY HALL' AND UPPER(PRE_DIR) = 'E'")
        self.assertEqual(norfolk_address_where('600 Granby Street'),"HSE_NUM = 600 AND UPPER(ST_NAME) = 'GRANBY'")
        self.assertIn("O''BRIEN",norfolk_address_where("100 O'Brien Rd"))
        with self.assertRaises(ValueError):norfolk_address_where('City Hall')

    def test_assessment_address_is_site_not_owner_address(self):
        row={'property_street_number':'800.0','property_street_direction':'E','property_street_name':'City Hall',
             'property_street_type':'AV','owner':'irrelevant','own_street':'999 OTHER CITY'}
        self.assertEqual(assessment_address(row),'800 E City Hall AV')
        self.assertNotIn('owner',ASSESSMENT_FIELDS)

    def test_residential_norfolk_classes_fail_even_when_buildings_are_large(self):
        rows=[assessment('Single Family - Detached','510 S/F Detached'),
              assessment('Single Family - Attached','511 S/F Attached (Townhome)'),
              assessment('Duplex','520 Res Duplex Designed'),assessment('Triplex','530 Res Triplex Designed'),
              assessment('Fourplex','540 Res Fourplex Designed'),assessment('Co-op','558 Co-op'),
              assessment('Condominium','550 Res 2-4 Condo Designed'),assessment('Apartment','407 Apartment 49+ High Rise'),
              assessment('Residential Outbuilding','522 Residential Outbuilding'),
              assessment('Non-Taxable','622 NRHA Residential'),assessment('Non-Taxable','612 Norfolk Residential'),
              assessment('Non-Taxable','602 Federal Residential'),assessment('Non-Taxable','692 HOA'),
              assessment('Non-Taxable','672 Religious Churches Resid')]
        for row in rows:
            with self.subTest(row=row):
                self.assertFalse(app.prescreen(site_for(row,50000),10000)[0])

    def test_commercial_condo_does_not_become_residential(self):
        z=site_for(assessment('Commercial','450 Com Condominium'),12000)
        self.assertNotIn('CONDO',z['land']);self.assertTrue(app.prescreen(z,10000)[0])

    def test_mini_warehouse_is_storage_not_warehouse_priority(self):
        z=site_for(assessment('Commercial','485 Com Mini Warehouse'),50000)
        self.assertEqual(z['land'],'SELF STORAGE')
        self.assertFalse(app.prescreen(z,10000)[0]);self.assertFalse(app.thermal_rescue_eligible(z))
        z=site_for(assessment('Commercial','480 Commercial Warehouse'),3000)
        self.assertTrue(app.prescreen(z,10000)[0]);self.assertTrue(app.thermal_rescue_eligible(z))

    def test_priority_norfolk_classes_keep_small_site_rescue(self):
        rows=[assessment('Commercial','414 Commercial Hospital'),assessment('Commercial','442 Com Medical Clinic/Office'),
              assessment('Industrial','340 Ind Lt Mfg/Assembly'),assessment('Non-Taxable','607 State Education ODU'),
              assessment('Non-Taxable','608 State Education NSU'),assessment('Non-Taxable','613 Norfolk City Schools'),
              assessment('Non-Taxable','611 Norfolk General Municipal'),assessment('Non-Taxable','643 Pump Station'),
              assessment('Non-Taxable','644 Public Utility'),assessment('Non-Taxable','667 EVMA Health Care')]
        for row in rows:
            with self.subTest(row=row):
                z=site_for(row);self.assertTrue(app.prescreen(z,10000)[0]);self.assertTrue(app.thermal_rescue_eligible(z))
        self.assertEqual(app.campus_buffer_ft(site_for(rows[3])),180)

    def test_city_building_codes_preserve_institutional_but_not_false_industrial_context(self):
        self.assertEqual(NORFOLK_BUILDING_CONTEXT[2022],'UNIVERSITY')
        self.assertEqual(NORFOLK_BUILDING_CONTEXT[2023],'HOSPITAL')
        self.assertNotIn('INDUSTR',NORFOLK_BUILDING_CONTEXT[2010])
        self.assertNotIn(2050,NORFOLK_BUILDING_CONTEXT);self.assertNotIn(2060,NORFOLK_BUILDING_CONTEXT)

    def test_retail_and_restaurant_spelling_variants_do_not_get_rescue(self):
        for code,desc in ((421,'Supermarket'),(436,'Fast Food Resturant'),(438,'Convenience Store w/Gas'),(418,'Retail/Apartment Over')):
            with self.subTest(code=code):
                z=site_for(assessment('Commercial',f'{code} {desc}'),12000)
                self.assertFalse(app.prescreen(z,10000)[0]);self.assertFalse(app.thermal_rescue_eligible(z))

    def test_exempt_is_not_automatically_military_or_public(self):
        z=site_for(assessment('Non-Taxable','999 Unrecognized exempt class'))
        self.assertEqual(z['land'],'UNKNOWN EXEMPT USE')
        self.assertFalse(app.thermal_rescue_eligible(z));self.assertFalse(app.prescreen(z,10000)[0])

    def test_one_good_campus_improvement_beats_vacant_or_residential_extension(self):
        records=[assessment('Vacant Land','300 Industrial Vacant Land',extension='L00'),
                 assessment('Duplex','520 Res Duplex Designed',extension='R01'),
                 assessment('Industrial','340 Ind Lt Mfg/Assembly',extension='C01')]
        for order in (records,list(reversed(records))):
            self.assertEqual(assessment_choice(order)['extension'],'C01')

    def test_public_land_ownership_does_not_erase_actual_improvement_use(self):
        land=assessment('Non-Taxable','621 NRHA General Municipal',extension='L00')
        for building in (assessment('Commercial','411 Commercial Hotels',extension='C01'),
                         assessment('Apartment','405 Apartment 49+ Low Rise',extension='C01')):
            with self.subTest(building=building):
                chosen=assessment_choice([land,building]);self.assertEqual(chosen,building)
        self.assertFalse(app.prescreen(site_for(assessment_choice([land,assessment('Apartment','405 Apartment 49+ Low Rise',extension='C01')]),50000),10000)[0])

    def test_unmatched_parcel_is_unknown_and_audited(self):
        z={'gpin':'1437152565','address':'GPIN 1437152565','land':'','territory':'norfolk'}
        app.enrich_norfolk_parcels([z],{})
        self.assertEqual(z['land'],'UNKNOWN');self.assertFalse(z['assessment_matched'])
        self.assertIn('FY27',z['assessment_source'])


class TerritoryRoutingTests(unittest.TestCase):
    def test_norfolk_geocode_uses_city_address_layer(self):
        hit={'attributes':{'FULL_ADD':'800 E CITY HALL AVENUE'},'geometry':{'x':-76.2846,'y':36.8471}}
        with patch.object(app,'gj',return_value={'features':[hit]}) as request:
            self.assertEqual(app.geocode('800 E City Hall Ave','norfolk'),(-76.2846,36.8471))
        url,params=request.call_args.args
        self.assertEqual(url,get_profile('norfolk')['address']);self.assertEqual(params['outSR'],'4326')
        self.assertIn('HSE_NUM = 800',params['where'])

    def test_geocode_ambiguity_requires_full_address(self):
        hits=[{'attributes':{'FULL_ADD':a},'geometry':{'x':x,'y':36.85}} for a,x in
              (('100 E MAIN STREET',-76.28),('100 W MAIN STREET',-76.29))]
        with patch.object(app,'gj',return_value={'features':hits}):
            with self.assertRaisesRegex(RuntimeError,'More than one'):app.geocode('100 Main St','norfolk')
            self.assertEqual(app.geocode('100 E Main St','norfolk'),(-76.28,36.85))

    def test_vb_geocode_keeps_original_search_contract(self):
        meta={'fields':[{'name':'FULL_ADDR','type':'esriFieldTypeString'}]}
        hits={'features':[{'geometry':{'x':-76,'y':36.8}}]}
        with patch.object(app,'gj',side_effect=[meta,hits]) as request:
            self.assertEqual(app.geocode('717 General Booth Blvd'),(-76,36.8))
        self.assertEqual(request.call_args.args[0],get_profile()['address'])
        self.assertIn("LIKE UPPER('%717 General Booth Blvd%')",request.call_args.args[1]['where'])

    def test_norfolk_parcel_join_uses_gpin_and_4326_geometry(self):
        feature={'attributes':{'GPIN':'1437152565','OBJECTID':7,'TAX_ACCT':'0007'},'geometry':{'rings':[square()]}}
        record=assessment('Non-Taxable','611 Norfolk General Municipal',gpin='1437152565',property_street_number='800',property_street_name='City Hall',property_street_direction='E',property_street_type='AV')
        with patch.object(app,'pages',return_value=[feature]) as query,patch.object(app,'load_norfolk_assessments',return_value={'1437152565':[record]}):
            rows=app.load_parcels(-76.28,36.85,.5,'norfolk')
        self.assertEqual(rows[0]['address'],'800 E City Hall AV');self.assertEqual(rows[0]['land'],'GOVERNMENT')
        self.assertTrue(rows[0]['assessment_matched']);self.assertEqual(query.call_args.args[1]['outSR'],'4326')
        self.assertEqual(query.call_args.kwargs['chunk'],1000)

    def test_multi_part_norfolk_parcel_keeps_all_rings(self):
        features=[{'attributes':{'GPIN':'123','OBJECTID':n},'geometry':{'rings':[square(side=n*100)]}} for n in (1,2)]
        with patch.object(app,'pages',return_value=features),patch.object(app,'load_norfolk_assessments',return_value={}):
            rows=app.load_parcels(-76.28,36.85,.5,'norfolk')
        self.assertEqual(len(rows),1);self.assertEqual(len(rows[0]['rings']),2)

    def test_norfolk_parcel_strict_radius_is_preserved(self):
        feature={'attributes':{'GPIN':'123','OBJECTID':1},'geometry':{'rings':[square(lon=-76.30)]}}
        with patch.object(app,'pages',return_value=[feature]),patch.object(app,'load_norfolk_assessments',return_value={}):
            self.assertEqual(app.load_parcels(-76.28,36.85,.5,'norfolk'),[])

    def test_assessment_fetch_is_batched_not_per_property(self):
        with patch.object(app,'gj',return_value=[]) as request:
            app.load_norfolk_assessments([str(1000000000+n) for n in range(301)])
        self.assertEqual(request.call_count,3)
        for call in request.call_args_list:
            self.assertEqual(call.args[0],get_profile('norfolk')['assessment'])
            self.assertNotIn('owner',call.args[1]['$select'])
            self.assertLessEqual(call.args[1]['$where'].count(',')+1,150)

    def test_assessment_pagination_and_error_handling(self):
        record={'gpin':'123'}
        with patch.object(app,'gj',side_effect=[[record]*2000,[record]]) as request:
            self.assertEqual(len(app.load_norfolk_assessments(['123'])['123']),2001)
        self.assertEqual(request.call_args_list[1].args[1]['$offset'],2000)
        with patch.object(app,'gj',return_value={'message':'broken'}):
            with self.assertRaisesRegex(RuntimeError,'stopped before prescreening'):app.load_norfolk_assessments(['123'])

    def test_norfolk_building_source_filters_demolished_and_has_safe_fallback(self):
        with patch.object(app,'_query_buildings',return_value=[{'sq':12000}]) as query:
            _,source,errors=app.load_buildings(-76.28,36.85,.5,'norfolk')
        self.assertEqual(source,'NORFOLK CITY');self.assertFalse(errors)
        args=query.call_args.args;self.assertEqual(args[0],get_profile('norfolk')['building'])
        self.assertIn('DEMO',args[5]);self.assertEqual(args[6],1000)
        with patch.object(app,'_query_buildings',side_effect=[RuntimeError('city service down'),[{'sq':12000}]]):
            _,source,errors=app.load_buildings(-76.28,36.85,.5,'norfolk')
        self.assertEqual(source,'VA CIVILREF');self.assertIn('city service down',errors[0])

    def test_norfolk_no_footprints_stops_before_false_quiet_prescreen(self):
        with patch.object(app,'load_parcels',return_value=[]),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([],'NONE',['service down'])):
            with self.assertRaisesRegex(RuntimeError,'stopped before prescreening'):app.discover(-76.28,36.85,.5,10000,'norfolk')

    def test_discovery_records_candidate_cap_and_unmatched(self):
        parcels=[{'gpin':str(n),'address':f'{n} Test Rd','land':'UNKNOWN','zone':'','lon':-76.28,'lat':36.85,'rings':[square()], 'psq':10000,'assessment_matched':False} for n in range(251)]
        report={}
        with patch.object(app,'load_parcels',return_value=parcels),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([{'lon':-76.28,'lat':36.85,'sq':12000,'rings':[square()], 'fcode':''}],'NORFOLK CITY',[])):
            rows,*_=app.discover(-76.28,36.85,.5,10000,'norfolk',report)
        self.assertEqual(len(rows),250);self.assertTrue(report['truncated'])
        self.assertEqual(report['candidates_before_limit'],251);self.assertEqual(report['assessment_unmatched'],251)


class ImageryAndAuditTests(unittest.TestCase):
    def test_same_projected_frame_and_pixels_across_cities(self):
        vb,vp=app.image_request_params(-76.28,36.85,1000)
        nf,np=app.image_request_params(-76.28,36.85,1000,territory='norfolk')
        self.assertNotEqual(vb,nf)
        for key in ('bbox','bboxSR','imageSR','size','format'):
            self.assertEqual(vp[key],np[key])
        bounds=[float(x) for x in np['bbox'].split(',')]
        self.assertAlmostEqual(bounds[2]-bounds[0],304.8,places=5)
        self.assertEqual(np['layers'],'show:0')

    def test_source_fields_are_not_driven_by_current_selector(self):
        self.assertEqual(app.csv_source_fields({'territory':'norfolk'})['city'],'Norfolk')
        self.assertEqual(app.csv_source_fields({})['city'],'Virginia Beach')

    def test_scan_metadata_identifies_frozen_baseline_and_sources(self):
        d=app.make_scan_metadata([{'territory':'norfolk'}],{'truncated':True})
        self.assertEqual(d['detector_baseline_version'],'0.11.7');self.assertEqual(d['model_pipeline_version'],'0.0.12')
        self.assertEqual(d['data_sources'][0]['city'],'Norfolk');self.assertTrue(d['discovery']['truncated'])

    def test_all_campus_views_use_the_row_territory_and_manifest(self):
        z={'territory':'norfolk','address':'800 E City Hall AV','lon':-76.28,'lat':36.85,'rings':[square(side=300)],
           'psq':90000,'count':1,'largest':10000,'land':'GOVERNMENT',
           'buildings':[{'lon':-76.28,'lat':36.85,'sq':10000,'rings':[square()]}]}
        with tempfile.TemporaryDirectory() as td,patch.object(app,'aerial_side') as download:
            views=app.campus_images(z,td);manifest=json.loads((Path(td)/'view_manifest.json').read_text())
        self.assertEqual([v['kind'] for v in views],['overview','building'])
        self.assertEqual(download.call_count,2)
        self.assertTrue(all(c.kwargs['territory']=='norfolk' for c in download.call_args_list))
        self.assertEqual(manifest['data_sources']['city'],'Norfolk')
        self.assertEqual(views[1]['pixels'],1800);self.assertEqual(views[1]['side_ft'],420)

    def test_arcgis_json_errors_are_not_saved_as_jpegs(self):
        response=io.BytesIO(b'{"error":{"message":"No coverage"}}')
        with tempfile.TemporaryDirectory() as td,patch.object(app.urllib.request,'urlopen',return_value=response):
            out=Path(td)/'test.jpg'
            with self.assertRaisesRegex(RuntimeError,'No coverage'):app.download_image('https://example.test',{},out,1800)
            self.assertFalse(out.exists())

    def test_blank_and_wrong_size_exports_stop_before_inference(self):
        for size,color in (((18,18),'white'),((1800,1800),'black')):
            with self.subTest(size=size),tempfile.TemporaryDirectory() as td:
                raw=io.BytesIO();Image.new('RGB',size,color).save(raw,format='JPEG');raw.seek(0)
                with patch.object(app.urllib.request,'urlopen',return_value=raw):
                    with self.assertRaises(RuntimeError):app.download_image('https://example.test',{},Path(td)/'test.jpg',1800)


class _Var:
    def __init__(self,**kwargs):self.value=kwargs.get('value')
    def get(self):return self.value
    def set(self,value):self.value=value


class _Widget:
    def __init__(self,*args,**kwargs):self.options=kwargs;self.items={}
    def pack(self,**kwargs):pass
    def grid(self,**kwargs):pass
    def bind(self,*args):pass
    def heading(self,*args,**kwargs):pass
    def column(self,*args,**kwargs):pass
    def config(self,**kwargs):self.options.update(kwargs)
    def get_children(self):return list(self.items)
    def delete(self,key):self.items.pop(key,None)
    def insert(self,*args,**kwargs):self.items[kwargs.get('iid')]=kwargs.get('values')
    def selection(self):return []


class _Root:
    def title(self,text):self.title_text=text
    def geometry(self,text):pass
    def after(self,delay,callback):callback()


class AppStateTests(unittest.TestCase):
    def setUp(self):
        self.patchers=[patch.object(app.tk,'StringVar',_Var)]
        self.patchers += [patch.object(app.ttk,name,_Widget) for name in
                          ('Frame','Label','Entry','Combobox','Button','Treeview','Separator')]
        for patcher in self.patchers:patcher.start();self.addCleanup(patcher.stop)
        self.ui=app.App(_Root())

    def test_default_and_city_change_do_not_mix_existing_rows(self):
        self.assertEqual(self.ui.active_territory,'norfolk');self.assertEqual(self.ui.rad.get(),'0.5')
        self.ui.rows=[{'address':'Old Norfolk property'}];self.ui.last_scan_root='old';self.ui.review_csv_path='old'
        self.ui.city.set('Virginia Beach');self.ui.change_city()
        self.assertEqual(self.ui.active_territory,'virginia_beach');self.assertEqual(self.ui.rad.get(),'1.0')
        self.assertEqual(self.ui.rows,[]);self.assertIsNone(self.ui.last_scan_root);self.assertIsNone(self.ui.review_csv_path)

    def test_city_discovery_and_scan_controls_lock_during_work(self):
        self.ui.set_busy(True)
        for widget in (self.ui.cityb,self.ui.discb,self.ui.scanb,self.ui.openb,self.ui.selb):
            self.assertEqual(widget.options['state'],'disabled')
        self.ui.scan_running=True;self.ui.city.set('Virginia Beach');self.ui.change_city()
        self.assertEqual(self.ui.active_territory,'norfolk');self.assertEqual(self.ui.city.get(),'Norfolk')
        self.ui.scan_running=False;self.ui.set_busy(False)
        self.assertEqual(self.ui.cityb.options['state'],'readonly')

    def test_saved_csv_cannot_be_reanalyzed_without_attribution_geometry(self):
        with patch.object(app.messagebox,'showinfo') as info,patch.object(app.threading,'Thread') as thread:
            self.ui.begin_scan([{'territory':'norfolk','lon':-76.28,'lat':36.85}])
        self.assertTrue(info.called);self.assertFalse(thread.called);self.assertFalse(self.ui.scan_running)

    def test_completed_scan_worker_writes_city_audit_and_unlocks_controls(self):
        z={'territory':'norfolk','city':'Norfolk','address':'Test property','gpin':'123','land':'GOVERNMENT',
           'lon':-76.28,'lat':36.85,'rings':[square()],'psq':10000,'pre':True,'score':60,'largest':10000,
           'source':'NORFOLK CITY','assessment_matched':True}
        self.ui.rows=[z];self.ui.scan_running=True
        cv={'detections':[],'max_prob':0,'stage1_proposals':0,'retained_evidence':0,'by_type':{}}
        engine=Mock();engine.scan_property.return_value=cv
        def campus_stub(site,root):Path(root).mkdir(parents=True,exist_ok=True);return []
        with tempfile.TemporaryDirectory() as td,patch.object(Path,'home',return_value=Path(td)),patch.object(self.ui,'engine',return_value=engine),patch.object(app,'campus_images',side_effect=campus_stub),patch.object(app.messagebox,'showinfo'),patch.object(app.messagebox,'showerror') as error:
            self.ui.scan_worker([z]);self.assertFalse(error.called)
            metadata=json.loads((self.ui.last_scan_root/'SCAN_METADATA.json').read_text())
            self.assertEqual(metadata['state'],'completed');self.assertEqual(metadata['data_sources'][0]['city'],'Norfolk')
            self.assertTrue((self.ui.last_scan_root/'DISCOVERY_AUDIT.json').exists())
            with self.ui.review_csv_path.open(newline='') as file:result=list(app.csv.DictReader(file))[0]
            self.assertEqual(result['territory'],'norfolk');self.assertEqual(result['cv_status'],'QUIET')
            cvpath=next(self.ui.last_scan_root.glob('*/cv_result.json'))
            self.assertEqual(json.loads(cvpath.read_text())['data_sources']['city'],'Norfolk')
        self.assertFalse(self.ui.scan_running);self.assertEqual(self.ui.cityb.options['state'],'readonly')

    def test_scan_failure_preserves_diagnostic_and_releases_controls(self):
        self.ui.scan_running=True
        with tempfile.TemporaryDirectory() as td,patch.object(Path,'home',return_value=Path(td)),patch.object(self.ui,'engine',side_effect=RuntimeError('test model startup failure')),patch.object(app.messagebox,'showerror') as error:
            self.ui.scan_worker([{'territory':'norfolk'}]);self.assertTrue(error.called)
            self.assertEqual(json.loads((self.ui.last_scan_root/'SCAN_METADATA.json').read_text())['state'],'failed')
            self.assertTrue((Path(td)/'Downloads/HVAC_CV_ERROR.txt').exists())
        self.assertFalse(self.ui.scan_running);self.assertEqual(self.ui.cityb.options['state'],'readonly')


if __name__=='__main__':
    unittest.main()
