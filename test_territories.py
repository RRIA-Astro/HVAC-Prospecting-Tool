import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

from PIL import Image

import app
from territories import (ASSESSMENT_FIELDS,PROFILES,NORFOLK_BUILDING_CONTEXT,CHESAPEAKE_BUILDING_CONTEXT,
                         NEWPORT_NEWS_BUILDING_CONTEXT,HAMPTON_BUILDING_CONTEXT,assessment_address,assessment_choice,canonical_address,
                         chesapeake_address_where,chesapeake_land_use,get_profile,newport_news_address_where,
                         newport_news_land_use,hampton_address_where,hampton_land_use,norfolk_address_where,norfolk_land_use,numeric_id)


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
        vb,nf,ch,nn,hm=(get_profile(),get_profile('norfolk'),get_profile('chesapeake'),
                        get_profile('newport_news'),get_profile('hampton'))
        for field in ('address','parcel','building'):
            self.assertEqual(len({vb[field],nf[field],ch[field],nn[field],hm[field]}),5)
        self.assertEqual(nf['imagery_kind'],'map_server')
        self.assertEqual(vb['imagery_kind'],'image_server')
        self.assertIn('/AerialPhotos/2025/MapServer/export',nf['imagery'])
        self.assertNotIn('norfolk',vb['imagery'])
        self.assertIn('qva7-tzrf',nf['assessment'])
        self.assertIn('/OpenData/OpenData/MapServer/15/query',ch['parcel'])
        self.assertIn('MostRecentImagery_WGS/MapServer/export',ch['imagery'])
        self.assertIn('/Operational/EnerGov/MapServer/6/query',nn['parcel'])
        self.assertIn('/Operational/EnerGov/MapServer/11/query',nn['building'])
        self.assertEqual(nn['imagery'],ch['imagery'])
        self.assertIn('/Aerials_2026/MapServer/export',hm['imagery'])
        self.assertEqual(hm['imagery_layers'],'show:13')
        self.assertFalse(ch['enabled']);self.assertFalse(nn['enabled']);self.assertTrue(hm['require_buildings'])

    def test_unknown_territory_never_silently_uses_vb(self):
        with self.assertRaisesRegex(ValueError,'Unsupported territory'):get_profile('portsmouth')
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
        self.assertEqual(chesapeake_address_where('306 Cedar Road, Chesapeake, VA 23322'),
                         "UPPER(ADDRESS) LIKE '306 CEDAR RD%'")
        self.assertEqual(newport_news_address_where('500 J Clyde Morris Boulevard, Newport News, VA 23601'),
                         "UPPER(FULLADDR) LIKE '500 J CLYDE MORRIS BLVD%'")
        self.assertEqual(hampton_address_where('3000 Coliseum Drive, Hampton, VA 23666'),
                         "UPPER(FullAdd) LIKE '3000 COLISEUM DR%'")

    def test_chesapeake_class_and_building_context_is_descriptive(self):
        classes={'4341':'COMMERCIAL - MEDICAL OFFICE','1010':'RESIDENTIAL - SINGLE FAMILY'}
        medical=chesapeake_land_use({'PROPCLASS':'4341','PROJECT':'Greenbrier Medical'},classes)
        home=chesapeake_land_use({'PROPCLASS':'1010'},classes)
        self.assertIn('MEDICAL',medical);self.assertIn('GREENBRIER MEDICAL',medical)
        self.assertFalse(app.prescreen({'land':home,'zone':'','facility':'','facility_kind':'','fcodes':[],
                                        'largest':50000,'avg':50000,'count':1,'buildings':[]},10000)[0])
        self.assertEqual(CHESAPEAKE_BUILDING_CONTEXT[3],'MEDICAL')
        self.assertEqual(CHESAPEAKE_BUILDING_CONTEXT[10],'HOSPITALITY HOTEL')
        self.assertEqual(CHESAPEAKE_BUILDING_CONTEXT[12],'INDUSTRIAL')
        self.assertNotIn('RESIDENTIAL',CHESAPEAKE_BUILDING_CONTEXT[1])

    def test_newport_news_assessment_and_building_context_is_auditable(self):
        attributes={'ASMT_LANDUSE':'Hospital','USEDSCRP':'HOSPITAL','CLASSDSCRP':'Commercial',
                    'VACANT':'N'}
        self.assertEqual(newport_news_land_use(attributes),'HOSPITAL | COMMERCIAL')
        self.assertIn('VACANT LAND',newport_news_land_use({'USEDSCRP':'Industrial','VACANT':'Y'}))
        self.assertEqual(NEWPORT_NEWS_BUILDING_CONTEXT['2'],'COMMERCIAL BUILDING')
        self.assertEqual(NEWPORT_NEWS_BUILDING_CONTEXT['3'],'PUBLIC BUILDING')

    def test_hampton_assessment_prefers_nonresidential_campus_improvements(self):
        rows=[{'ImprType':'DWELLING','UseDesc':'Dormitory','ImpStat':'A'},
              {'ImprType':'COMMERCIAL','UseDesc':'Hospital','ImpStat':'A'},
              {'ImprType':'COMMERCIAL','UseDesc':'Laboratory','ImpStat':'A'},
              {'ImprType':'COMMERCIAL','UseDesc':'Old Office','ImpStat':'I'}]
        land=hampton_land_use(rows)
        self.assertEqual(land,'HOSPITAL | LABORATORY')
        self.assertNotIn('DORMITORY',land);self.assertNotIn('OLD OFFICE',land)
        self.assertEqual(HAMPTON_BUILDING_CONTEXT[1810],'NONRESIDENTIAL BUILDING')

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

    def test_chesapeake_geocode_uses_exact_city_address_layer(self):
        hit={'attributes':{'ADDRESS':'306 CEDAR RD'},'geometry':{'x':-76.2497,'y':36.71577}}
        with patch.object(app,'gj',return_value={'features':[hit]}) as request:
            self.assertEqual(app.geocode('306 Cedar Road','chesapeake'),(-76.2497,36.71577))
        url,params=request.call_args.args
        self.assertEqual(url,get_profile('chesapeake')['address'])
        self.assertEqual(params['where'],"UPPER(ADDRESS) LIKE '306 CEDAR RD%'")
        self.assertEqual(params['outFields'],'ADDRESS');self.assertEqual(params['outSR'],'4326')

    def test_newport_news_geocode_uses_exact_city_address_layer(self):
        hit={'attributes':{'FULLADDR':'500 J CLYDE MORRIS BLVD'},
             'geometry':{'x':-76.483036,'y':37.064294}}
        suite={'attributes':{'FULLADDR':'500 J CLYDE MORRIS BLVD, STE G'},
               'geometry':{'x':-76.482508,'y':37.065348}}
        with patch.object(app,'gj',return_value={'features':[hit,suite]}) as request:
            self.assertEqual(app.geocode('500 J Clyde Morris Blvd','newport_news'),(-76.483036,37.064294))
            self.assertEqual(app.geocode('500 J Clyde Morris Boulevard, Suite G','newport_news'),(-76.482508,37.065348))
        url,params=request.call_args.args
        self.assertEqual(url,get_profile('newport_news')['address'])
        self.assertEqual(params['where'],"UPPER(FULLADDR) LIKE '500 J CLYDE MORRIS BLVD%'")
        self.assertEqual(params['outFields'],'FULLADDR');self.assertEqual(params['outSR'],'4326')

    def test_hampton_geocode_prefers_main_nonleasehold_point(self):
        lease={'attributes':{'OBJECTID':2,'GISLRSN':'13003528','FullAdd':'3000 COLISEUM DR',
                             'PlaceName':'LEASEHOLD','PlaceName2':'Sentara Careplex','CLASS':1},
               'geometry':{'x':-76.38980,'y':37.05707}}
        main={'attributes':{'OBJECTID':1,'GISLRSN':'7001649','FullAdd':'3000 COLISEUM DR',
                            'PlaceName':'','PlaceName2':'Sentara Careplex','CLASS':1},
              'geometry':{'x':-76.39065,'y':37.05681}}
        with patch.object(app,'gj',return_value={'features':[lease,main]}) as request:
            self.assertEqual(app.geocode('3000 Coliseum Dr','hampton'),(-76.39065,37.05681))
        url,params=request.call_args.args
        self.assertEqual(url,get_profile('hampton')['address'])
        self.assertEqual(params['where'],"UPPER(FullAdd) LIKE '3000 COLISEUM DR%'")
        self.assertIn('PlaceName2',params['outFields']);self.assertEqual(params['outSR'],'4326')

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

    def test_chesapeake_parcel_uses_class_table_and_official_project(self):
        feature={'attributes':{'OBJECTID':8,'MAP_PARCEL':'0470000000830','ADDRESS':'208  CONQUEST DR ',
                               'UNIT':'','PROJECT':'CITY HALL COMPLEX','PROPCLASS':'7410',
                               'ASSESSMNT_DIST':'CEDAR ROAD CORRIDOR'},'geometry':{'rings':[square()]}}
        classes={'7410':'EXEMPT - CHESAPEAKE GOVERNMENT'}
        with patch.object(app,'load_chesapeake_classes',return_value=classes),patch.object(app,'pages',return_value=[feature]) as query:
            rows=app.load_parcels(-76.28,36.85,.5,'chesapeake')
        row=rows[0]
        self.assertEqual(row['gpin'],'0470000000830');self.assertEqual(row['address'],'208 CONQUEST DR')
        self.assertIn('CHESAPEAKE GOVERNMENT',row['land']);self.assertIn('CITY HALL COMPLEX',row['land'])
        self.assertEqual(row['facility_hint'],'CITY HALL COMPLEX');self.assertTrue(row['assessment_matched'])
        self.assertEqual(row['raw_classification'],'7410');self.assertEqual(query.call_args.args[1]['outSR'],'4326')

    def test_newport_news_official_place_and_parcel_are_joined_by_parcel_id(self):
        place={'attributes':{'OBJECTID':1,'PARCELID':'231000135','FULLADDR':'500 J CLYDE MORRIS BLVD',
                             'PLACENAME':'Riverside Regional Medical Center','ADDRCLASS':'PRIMARY'}}
        with patch.object(app,'pages',return_value=[place]) as query:
            places=app.load_newport_news_places(-76.4830,37.0643,.5)
        self.assertEqual(places['231000135']['facility'],'Riverside Regional Medical Center')
        self.assertEqual(query.call_args.args[0],get_profile('newport_news')['address'])
        self.assertEqual(query.call_args.args[1]['returnGeometry'],'false')

        feature={'attributes':{'OBJECTID':7,'PARCELID':'231000135','SITEADDRESS':'502 J CLYDE MORRIS BLVD',
                               'ASMT_LANDUSE':'Hospital','USECD':'600','USEDSCRP':'HOSPITAL',
                               'CLASSCD':'C','CLASSDSCRP':'Commercial','OWNERNME1':'Riverside',
                               'ZONE':'O2','VACANT':'N'},'geometry':{'rings':[square(lon=-76.4830,lat=37.0643)]}}
        with patch.object(app,'load_newport_news_places',return_value=places),patch.object(app,'pages',return_value=[feature]) as parcel_query:
            rows=app.load_parcels(-76.4830,37.0643,.5,'newport_news')
        row=rows[0]
        self.assertEqual(row['gpin'],'231000135');self.assertEqual(row['facility_hint'],'Riverside Regional Medical Center')
        self.assertEqual(row['address'],'502 J CLYDE MORRIS BLVD');self.assertEqual(row['land'],'HOSPITAL | COMMERCIAL')
        self.assertEqual(row['zone'],'O2');self.assertTrue(row['assessment_matched'])
        self.assertEqual(parcel_query.call_args.args[1]['outSR'],'4326')

    def test_hampton_official_place_assessment_and_parcel_are_joined_by_lrsn(self):
        places={'7001649':{'facility':'Sentara Careplex','address':'3000 COLISEUM DR'}}
        improvements={'7001649':[{'LRSN':7001649,'ImprType':'COMMERCIAL','UseCode':'HOSPITAL',
                                  'UseDesc':'Hospital','BldgType':'Hospital:001','FinSize':'249628',
                                  'ImpStat':'A','PropExt':'C01'}]}
        feature={'attributes':{'OBJECTID':7,'P_TYPE':0,'LRSNTXT':'7001649','LRSNINT':7001649,
                               'GPIN':'','SITUS':'3000 COLISEUM DR','SQFT':2243830,'ACREAGE':51},
                 'geometry':{'rings':[square(lon=-76.39065,lat=37.05681,side=500)]}}
        with patch.object(app,'load_hampton_places',return_value=places),\
             patch.object(app,'load_hampton_assessments',return_value=improvements),\
             patch.object(app,'pages',return_value=[feature]) as parcel_query:
            rows=app.load_parcels(-76.39065,37.05681,.5,'hampton')
        row=rows[0]
        self.assertEqual(row['gpin'],'7001649');self.assertEqual(row['facility_hint'],'Sentara Careplex')
        self.assertEqual(row['address'],'3000 COLISEUM DR');self.assertEqual(row['land'],'HOSPITAL')
        self.assertTrue(row['assessment_matched']);self.assertEqual(row['raw_classification'],'HOSPITAL')
        self.assertEqual(parcel_query.call_args.args[1]['outSR'],'4326')

    def test_hampton_assessment_fetch_is_batched(self):
        feature={'attributes':{'LRSN':7001649,'UseDesc':'Hospital'}}
        with patch.object(app,'pages',return_value=[feature]) as request:
            rows=app.load_hampton_assessments([str(7000000+n) for n in range(301)])
        self.assertEqual(request.call_count,3);self.assertIn('7001649',rows)
        for call in request.call_args_list:
            self.assertEqual(call.args[0],get_profile('hampton')['assessment'])
            self.assertLessEqual(call.args[1]['where'].count(',')+1,150)

    def test_chesapeake_class_lookup_fails_closed_before_prescreen(self):
        with patch.object(app,'gj',return_value={'features':[]}):
            with self.assertRaisesRegex(RuntimeError,'stopped before prescreening'):app.load_chesapeake_classes()

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

    def test_chesapeake_building_codes_and_names_are_retained(self):
        feature={'attributes':{'OBJECTID':9,'BUILDINGCLASS':3,'NAME':'Regional Medical Center'},
                 'geometry':{'rings':[square(side=200)]}}
        with patch.object(app,'pages',return_value=[feature]):
            rows=app._query_buildings(get_profile('chesapeake')['building'],-76.28,36.85,.5,'*',city='chesapeake')
        self.assertEqual(rows[0]['fcode'],'MEDICAL');self.assertEqual(rows[0]['feature_code'],3)
        self.assertEqual(rows[0]['name'],'Regional Medical Center')

    def test_newport_news_building_codes_and_height_are_retained(self):
        feature={'attributes':{'OBJECTID':9,'FEATURECODE':2,'BLDGHEIGHT':48,'FLOORCOUNT':4},
                 'geometry':{'rings':[square(lon=-76.4830,lat=37.0643,side=200)]}}
        with patch.object(app,'pages',return_value=[feature]):
            rows=app._query_buildings(get_profile('newport_news')['building'],-76.4830,37.0643,.5,'*',city='newport_news')
        self.assertEqual(rows[0]['fcode'],'COMMERCIAL BUILDING');self.assertEqual(rows[0]['feature_code'],'2')
        self.assertEqual(rows[0]['height'],48)

    def test_hampton_building_domain_and_nonbuilding_filter_are_retained(self):
        feature={'attributes':{'OBJECTID':9,'S_TYPE':1810},
                 'geometry':{'rings':[square(lon=-76.39065,lat=37.05681,side=200)]}}
        with patch.object(app,'pages',return_value=[feature]):
            rows=app._query_buildings(get_profile('hampton')['building'],-76.39065,37.05681,.5,'*',city='hampton')
        self.assertEqual(rows[0]['fcode'],'NONRESIDENTIAL BUILDING');self.assertEqual(rows[0]['feature_code'],1810)
        with patch.object(app,'_query_buildings',return_value=rows) as query:
            _,source,_=app.load_buildings(-76.39065,37.05681,.5,'hampton')
        self.assertEqual(source,'HAMPTON CITY');self.assertIn('S_TYPE IN',query.call_args.args[5])

    def test_norfolk_no_footprints_stops_before_false_quiet_prescreen(self):
        with patch.object(app,'load_parcels',return_value=[]),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([],'NONE',['service down'])):
            with self.assertRaisesRegex(RuntimeError,'stopped before prescreening'):app.discover(-76.28,36.85,.5,10000,'norfolk')

    def test_chesapeake_no_footprints_stops_before_false_quiet_prescreen(self):
        with patch.object(app,'load_parcels',return_value=[]),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([],'NONE',['service down'])):
            with self.assertRaisesRegex(RuntimeError,'Chesapeake building footprints.*stopped before prescreening'):
                app.discover(-76.28,36.85,.5,10000,'chesapeake')

    def test_newport_news_no_footprints_stops_before_false_quiet_prescreen(self):
        with patch.object(app,'load_parcels',return_value=[]),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([],'NONE',['service down'])):
            with self.assertRaisesRegex(RuntimeError,'Newport News building footprints.*stopped before prescreening'):
                app.discover(-76.4830,37.0643,.5,10000,'newport_news')

    def test_hampton_no_footprints_stops_before_false_quiet_prescreen(self):
        with patch.object(app,'load_parcels',return_value=[]),patch.object(app,'load_osm_names',return_value=[]),patch.object(app,'load_buildings',return_value=([],'NONE',['service down'])):
            with self.assertRaisesRegex(RuntimeError,'Hampton building footprints.*stopped before prescreening'):
                app.discover(-76.39065,37.05681,.5,10000,'hampton')

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
        ch,cp=app.image_request_params(-76.28,36.85,1000,territory='chesapeake')
        nn,nnp=app.image_request_params(-76.4830,37.0643,1000,territory='newport_news')
        hm,hmp=app.image_request_params(-76.39065,37.05681,1000,territory='hampton')
        self.assertNotEqual(vb,nf)
        self.assertEqual(len({vb,nf,ch,hm}),4)
        self.assertEqual(nn,ch)
        for params in (np,cp,nnp,hmp):
            for key in ('bbox','bboxSR','imageSR','size','format'):
                if params in (nnp,hmp) and key=='bbox':continue
                self.assertEqual(vp[key],params[key])
        bounds=[float(x) for x in np['bbox'].split(',')]
        self.assertAlmostEqual(bounds[2]-bounds[0],304.8,places=5)
        self.assertEqual(np['layers'],'show:0');self.assertEqual(cp['layers'],'show:0')
        self.assertEqual(hmp['layers'],'show:13')

    def test_transient_503_is_retried_with_bounded_backoff(self):
        error=app.urllib.error.HTTPError('https://example.test',503,'temporarily unavailable',None,None)
        good=io.BytesIO(b'{"features":[]}')
        with patch.object(app.urllib.request,'urlopen',side_effect=[error,good]) as request,patch.object(app.time,'sleep') as sleep:
            self.assertEqual(app.gj('https://example.test',{'f':'json'}),{'features':[]})
        self.assertEqual(request.call_count,2);sleep.assert_called_once_with(1.0)

    def test_permanent_http_error_is_not_retried(self):
        error=app.urllib.error.HTTPError('https://example.test',404,'not found',None,None)
        with patch.object(app.urllib.request,'urlopen',side_effect=error) as request,patch.object(app.time,'sleep') as sleep:
            with self.assertRaises(app.urllib.error.HTTPError):app.gj('https://example.test',{'f':'json'})
        self.assertEqual(request.call_count,1);sleep.assert_not_called()

    def test_source_fields_are_not_driven_by_current_selector(self):
        self.assertEqual(app.csv_source_fields({'territory':'norfolk'})['city'],'Norfolk')
        self.assertEqual(app.csv_source_fields({'territory':'chesapeake'})['city'],'Chesapeake')
        self.assertEqual(app.csv_source_fields({'territory':'newport_news'})['city'],'Newport News')
        self.assertEqual(app.csv_source_fields({'territory':'hampton'})['city'],'Hampton')
        self.assertEqual(app.csv_source_fields({})['city'],'Virginia Beach')

    def test_scan_metadata_identifies_frozen_baseline_and_sources(self):
        d=app.make_scan_metadata([{'territory':'hampton'}],{'truncated':True})
        self.assertEqual(d['detector_baseline_version'],'0.11.7');self.assertEqual(d['model_pipeline_version'],'0.0.12')
        self.assertEqual(d['territory_logic_version'],'0.11.13')
        self.assertEqual(d['data_sources'][0]['city'],'Hampton');self.assertTrue(d['discovery']['truncated'])

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

    def test_dense_norfolk_hotel_gets_focus_view_but_vb_baseline_does_not_change(self):
        building={'lon':-76.28,'lat':36.85,'sq':72554,'rings':[square(side=250)]}
        base={'address':'777 Waterside DR','lon':-76.28,'lat':36.85,'rings':[square(side=400)],
              'psq':155494,'count':1,'largest':72554,'land':'HOTEL','zone':'','facility':'',
              'facility_kind':'','fcodes':[],'buildings':[building]}
        with tempfile.TemporaryDirectory() as td,patch.object(app,'aerial_side'):
            nf=app.campus_images(dict(base,territory='norfolk'),Path(td)/'nf')
            vb=app.campus_images(dict(base,territory='virginia_beach'),Path(td)/'vb')
        self.assertIn('building_focus',[v['kind'] for v in nf])
        self.assertNotIn('building_focus',[v['kind'] for v in vb])

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
        self.assertIn('Hampton',self.ui.cityb.options['values'])
        self.assertNotIn('Newport News',self.ui.cityb.options['values'])
        self.assertNotIn('Chesapeake',self.ui.cityb.options['values'])
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
