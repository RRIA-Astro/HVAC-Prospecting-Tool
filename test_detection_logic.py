import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import app


def detection(typ, p, best, long_ft, short_ft, *, bd=0, pd=0, kind="building_focus",
              seam=False, rescue=False, review=False, lon=-76.0, lat=36.8, scope="PARCEL"):
    return {
        "type": typ, "p": p, "best_class_prob": best, "long_ft": long_ft,
        "short_ft": short_ft, "building_distance_ft": bd, "parcel_distance_ft": pd,
        "lon": lon, "lat": lat, "view_kind": kind,
        "internal_tile_edge": seam, "rescue": rescue, "review_only": review,
        "attribution_scope": scope, "candidate": 0.5,
    }


def rectangle_building(lon=-76.0, lat=36.8, width=100, height=20, sq=2000):
    pts=[]
    for dx,dy in ((-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2),(-width/2,-height/2)):
        pts.append(app.lonlat_offset(lon,lat,dx,dy))
    return {"rings":[pts],"sq":sq,"lon":lon,"lat":lat}


class _Array:
    def __init__(self, value):self.value=np.asarray(value,dtype=np.float32)
    def detach(self):return self
    def cpu(self):return self
    def numpy(self):return self.value


class _Boxes:
    def __init__(self):
        self.xyxy=_Array([[320,320,640,640]])
        self.conf=_Array([0.2])


class _Result:
    def __init__(self, hit):self.boxes=_Boxes() if hit else None


class _Candidate:
    def predict(self, source, **kwargs):
        return [_Result("_x644_y644" in str(source))]


class FrozenDetectionLogicTests(unittest.TestCase):
    def test_frozen_primary_operating_points(self):
        self.assertEqual(app.DETECTOR_BASELINE_VERSION,"0.11.7")
        self.assertEqual(app.TERRITORY_LOGIC_VERSION,"0.11.16")
        self.assertEqual((app.CANDIDATE_THRESHOLD,app.TOWER_CHILLER_THRESHOLD,app.LARGE_PACKAGED_THRESHOLD),(.07,.35,.45))

    def test_5925_target_is_well_inside_a_zoom_crop(self):
        origins=app.LocalCV.__new__(app.LocalCV).perimeter_rescue_tile_origins(1800,1800)
        # Original-image coordinates of the side-yard fan bank in F02_138944sf.jpg.
        x,y=1535,935;t=app.PERIMETER_RESCUE_TILE_PX
        margins=[min(x-x0,y-y0,x0+t-x,y0+t-y) for x0,y0 in origins if x0<=x<=x0+t and y0<=y<=y0+t]
        self.assertGreaterEqual(max(margins),200)

    def test_norfolk_zoom_grid_closes_blind_bands_without_changing_vb(self):
        eng=app.LocalCV.__new__(app.LocalCV)
        vb=eng.perimeter_rescue_tile_origins(1800,1800,{"territory":"virginia_beach"})
        nf=eng.perimeter_rescue_tile_origins(1800,1800,{"territory":"norfolk"})
        self.assertEqual(len(vb),9);self.assertEqual(sorted({x for x,_ in vb}),[0,644,1288])
        self.assertEqual(len(nf),16);self.assertEqual(sorted({x for x,_ in nf}),[0,429,859,1288])
        axes=sorted({x for x,_ in nf})
        self.assertTrue(all(b-a<app.PERIMETER_RESCUE_TILE_PX for a,b in zip(axes,axes[1:])))
        self.assertEqual(axes[-1]+app.PERIMETER_RESCUE_TILE_PX,1800)

    def test_norfolk_hotel_rescue_is_urban_contextual_not_blanket(self):
        urban={"territory":"norfolk","land":"HOTEL","facility":"Sheraton Norfolk Waterside Hotel",
               "zone":"","facility_kind":"","fcodes":[],"largest":72554,"psq":155494,
               "count":1,"buildings":[]}
        suburban=dict(urban,facility="Suburban low-rise hotel",largest=45000,psq=250000)
        convention=dict(suburban,facility="Downtown Hotel and Convention Center")
        self.assertTrue(app.norfolk_urban_hotel(urban));self.assertTrue(app.thermal_rescue_eligible(urban))
        self.assertFalse(app.norfolk_urban_hotel(suburban));self.assertFalse(app.thermal_rescue_eligible(suburban))
        self.assertTrue(app.norfolk_urban_hotel(convention))
        self.assertFalse(app.norfolk_urban_hotel(dict(urban,territory="virginia_beach")))
        self.assertFalse(app.thermal_rescue_eligible(dict(urban,territory="virginia_beach")))
        self.assertEqual(app.mechanical_focus_min_ft2(urban),50000)
        self.assertEqual(app.mechanical_focus_min_ft2(suburban),75000)
        self.assertEqual(app.mechanical_focus_min_ft2(dict(urban,territory="virginia_beach")),75000)

    def test_norfolk_priority_focus_floor_covers_610_may_without_changing_vb(self):
        school={"territory":"norfolk","land":"SCHOOL","facility":"Ruffner Academy","zone":"",
                "facility_kind":"","fcodes":[],"largest":72444,"psq":427820}
        self.assertEqual(app.mechanical_focus_min_ft2(school),50000)
        self.assertEqual(app.mechanical_focus_min_ft2(dict(school,territory="virginia_beach")),75000)

    def test_norfolk_small_site_rescue_attribution_rejects_neighbor_only(self):
        site={"territory":"norfolk","land":"INDUSTRIAL","psq":46168,"count":1,"buildings":[{}]}
        neighbor={"parcel_ok":True,"parcel_distance_ft":20.637,"building_distance_ft":20.682}
        self.assertFalse(app.rescue_attribution_allowed(site,neighbor))
        self.assertTrue(app.rescue_attribution_allowed(site,dict(neighbor,parcel_distance_ft=0)))
        self.assertTrue(app.rescue_attribution_allowed(site,dict(neighbor,building_distance_ft=0)))
        self.assertTrue(app.rescue_attribution_allowed(dict(site,territory="virginia_beach"),neighbor))
        self.assertTrue(app.rescue_attribution_allowed(dict(site,psq=155494),neighbor))
        self.assertFalse(app.rescue_attribution_allowed(site,dict(neighbor,parcel_ok=False)))

    def test_zoom_detection_maps_back_to_source_coordinates(self):
        eng=app.LocalCV.__new__(app.LocalCV);eng.candidate=_Candidate()
        eng._rescue_candidate_audit=[]
        eng.verify=lambda *args:("COOLING_TOWER",.90,.10,True,.80)
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"test.jpg";Image.new("RGB",(1800,1800),"white").save(src)
            view={"path":str(src),"side_ft":1000/math.cos(math.radians(36.8)),"lat":36.8,"lon":-76.0,"kind":"building_focus"}
            z={"lat":36.8,"lon":-76.0,"rings":[],"buildings":[],"land":"INDUSTRIAL","largest":50000}
            ds,props,tiles,verified=eng.scan_perimeter_rescue_image(view,Path(td),z)
        self.assertEqual((props,tiles,verified),(1,9,1));self.assertEqual(len(ds),1)
        # 1800px/512px grid centers at x=y=644; the synthetic 320..640 box maps to 804..964.
        self.assertTrue(np.allclose(ds[0]["box"],(804,804,964,964)))
        self.assertTrue(ds[0]["review_only"] and ds[0]["perimeter_rescue"])
        self.assertEqual(eng._rescue_candidate_audit[0]["decision"],"RETAINED")

    def test_small_public_priority_site_receives_rescue(self):
        bs=[rectangle_building() for _ in range(10)]
        z={"land":"PUBLIC/SEMI PUBLIC","zone":"","facility":"","facility_kind":"","fcodes":[],
           "largest":10018,"avg":2000,"count":10,"buildings":bs}
        self.assertFalse(app.repetitive_storage_like(z));self.assertTrue(app.thermal_rescue_eligible(z))
        views=[{"kind":"building_focus","label":"BUILDING FOCUS 1","building":{"sq":10018}}]
        self.assertEqual(app.thermal_rescue_views(views,z),views)
        # Exercise the integrated fallback/counter path, not just its selectors.
        with tempfile.TemporaryDirectory() as td:
            image=Path(td)/"focus.jpg";Image.new("RGB",(1800,1800),"white").save(image)
            iview=dict(views[0],path=str(image),lon=-76.0,lat=36.8,side_ft=420)
            eng=app.LocalCV.__new__(app.LocalCV)
            eng.scan_image=lambda *args:(Image.open(image).convert("RGB"),[],0,[])
            eng.scan_rescue_image=lambda *args:([],0,5,0)
            micro={"box":(800,800,860,860),"type":"COOLING_TOWER","p":.75,"best_class_prob":.65,
                   "candidate":.01,"lon":-76.0,"lat":36.8,"width_ft":14,"height_ft":14,
                   "long_ft":14,"short_ft":14,"building_distance_ft":0,"attribution_scope":"PARCEL",
                   "rescue":True,"perimeter_rescue":True,"review_only":True,"internal_tile_edge":False}
            eng.scan_perimeter_rescue_image=lambda *args:([dict(micro)],1,9,1)
            cv=eng.scan_property([iview],Path(td)/"site",dict(z,lon=-76.0,lat=36.8,rings=[]))
        self.assertEqual((cv["perimeter_rescue_proposals"],cv["perimeter_rescue_tiles"],cv["perimeter_rescue_verified"]),(1,9,1))
        self.assertEqual(app.triage_status(z,cv),"REVIEW")

    def test_large_site_uses_two_focus_views(self):
        views=[{"kind":"overview","label":"O"},{"kind":"building_focus","label":"F01","building":{"sq":138944}},
               {"kind":"building_focus","label":"F02","building":{"sq":138944}}]
        self.assertEqual([v["label"] for v in app.thermal_rescue_views(views,{"largest":138944})],["F01","F02"])

    def test_norfolk_scope_rescue_covers_distinct_secondary_building(self):
        arena={"sq":94003,"lon":-76.2869,"lat":36.8533}
        tower_building={"sq":45227,"lon":-76.2861,"lat":36.8521}
        views=[{"kind":"overview","label":"O"},
               {"kind":"building_focus","label":"F01","building":arena},
               {"kind":"building","label":"B01","building":arena},
               {"kind":"building","label":"B02","building":tower_building}]
        chosen=app.thermal_rescue_views(views,{"territory":"norfolk","largest":94003})
        self.assertEqual([v["label"] for v in chosen],["F01","B02"])

    def test_norfolk_bank_street_building_owned_evidence_is_review_only(self):
        bank={"territory":"norfolk","land":"GOVERNMENT","facility":"Bank Street Garage",
              "zone":"","fcodes":[],"count":1,"largest":178447,"buildings":[]}
        self.assertTrue(app.norfolk_building_owned_review(bank,100.7,0.0))
        self.assertFalse(app.norfolk_building_owned_review(bank,151,0.0))
        self.assertFalse(app.norfolk_building_owned_review(bank,112.2,263.4))
        self.assertFalse(app.norfolk_building_owned_review(dict(bank,territory="virginia_beach"),100.7,0.0))
        tower_as_package=detection("LARGE_PACKAGED_HVAC",.9843,.7911,54.31,48.00,pd=99.97,bd=0,
                                   scope="BUILDING FOOTPRINT",review=True)
        tower_as_package["building_owned_review"]=True
        cv={"detections":[tower_as_package],"raw_detections":[tower_as_package]}
        self.assertTrue(app.package_rankable(bank,tower_as_package,cv))
        self.assertEqual(app.triage_status(bank,cv),"REVIEW")
        self.assertIn("Building-footprint review 1",app.hit_text(cv,bank))

    def test_norfolk_high_value_rescue_controls(self):
        def cv(primary,deep,zoom,outside=0):
            return {"detections":[],"raw_detections":[],"stage1_proposals":primary,
                    "deep_rescue_verified":deep,"perimeter_rescue_verified":zoom,
                    "attribution_rejected":outside}
        common={"territory":"norfolk","land":"GOVERNMENT","zone":"","fcodes":[],"buildings":[]}
        post=dict(common,facility="Norfolk Post Office",largest=213852)
        waterside=dict(common,facility="VIN Wine Bar",land="GOVERNMENT HOUSING AUTHORITY",largest=74459)
        scope=dict(common,facility="Scope Arena",largest=94003)
        adjoining=dict(common,facility="Town Point Garage",largest=53372)
        self.assertEqual(app.triage_status(post,cv(0,6,2)),"REVIEW")
        self.assertEqual(app.triage_status(waterside,cv(0,15,2)),"REVIEW")
        self.assertEqual(app.triage_status(scope,cv(2,1,3,2)),"REVIEW")
        self.assertEqual(app.triage_status(adjoining,cv(17,7,1,13)),"QUIET")
        self.assertEqual(app.triage_status(dict(post,territory="virginia_beach"),cv(0,6,2)),"QUIET")
        self.assertIn("High-value rescue near miss 17",app.hit_text(cv(0,15,2),waterside))

    def test_large_public_seam_mechanical_candidate_is_review_only(self):
        museum={"territory":"portsmouth","land":"MUSEUM | EXEMPT COMMERCIAL | CITY OF PORTSMOUTH",
                "zone":"","facility":"Children's Museum","facility_kind":"","fcodes":[],
                "largest":65000,"count":1,"buildings":[]}
        package=detection("LARGE_PACKAGED_HVAC",.8845,.7984,69.2,33.7,bd=0,pd=12.6,
                          kind="overview",seam=True)
        cv={"detections":[package],"raw_detections":[package]}
        self.assertFalse(app.package_rankable(museum,package,cv))
        self.assertTrue(app.large_institutional_mechanical_review(museum,cv))
        self.assertEqual(app.triage_status(museum,cv),"REVIEW")
        self.assertIn("Large institutional mechanical candidate",app.hit_text(cv,museum))

        jail=dict(museum,facility="Portsmouth Jail",land="GOVERNMENT | CITY OF PORTSMOUTH",largest=120000)
        weaker=detection("LARGE_PACKAGED_HVAC",.6265,.2887,78.7,33.6,bd=0,pd=0,
                         kind="overview",seam=True)
        self.assertEqual(app.triage_status(jail,{"detections":[weaker],"raw_detections":[weaker]}),"REVIEW")

        controls=(dict(museum,land="COMMERCIAL WAREHOUSE",facility="Warehouse"),
                  dict(museum,largest=49999),dict(museum,territory="virginia_beach"))
        for site in controls:
            with self.subTest(site=site):self.assertEqual(app.triage_status(site,cv),"QUIET")
        for changed in (dict(package,building_distance_ft=2),dict(package,best_class_prob=.279),dict(package,long_ft=59.9)):
            with self.subTest(detection=changed):
                self.assertEqual(app.triage_status(museum,{"detections":[changed],"raw_detections":[changed]}),"QUIET")
        nonseam=dict(package,internal_tile_edge=False)
        self.assertFalse(app.large_institutional_mechanical_review(museum,{"detections":[nonseam]}))
        self.assertEqual(app.triage_status(museum,{"detections":[nonseam],"raw_detections":[nonseam]}),"STRONG")

    def test_830_small_warehouse_isolated_perimeter_clutter_is_quiet(self):
        site={"territory":"norfolk","land":"COMMERCIAL - STORAGE WAREHOUSE","zone":"",
              "facility":"","facility_kind":"","fcodes":[],"largest":10625,"count":1,"buildings":[]}
        clutter=detection("COOLING_TOWER",.91,.75,9.28,6.37,bd=31.8,rescue=True,review=True)
        clutter["perimeter_rescue"]=True
        cv={"detections":[clutter],"raw_detections":[clutter]}
        self.assertTrue(app.thermal_detection_rankable(site,clutter))
        self.assertTrue(app.norfolk_small_warehouse_clutter_reject(site,clutter,[clutter]))
        self.assertEqual(app.triage_status(site,cv),"QUIET")
        self.assertEqual(app.triage_status(dict(site,territory="chesapeake"),cv),"REVIEW")
        larger=dict(clutter,long_ft=12.0)
        self.assertFalse(app.norfolk_small_warehouse_clutter_reject(site,larger,[larger]))

    def test_large_medical_campus_gets_context_only_manual_review(self):
        cv={"detections":[],"raw_detections":[],"stage1_proposals":0,
            "deep_rescue_verified":0,"perimeter_rescue_verified":0,"attribution_rejected":0}
        site={"territory":"norfolk","land":"MEDICAL HEALTH CARE","zone":"","facility":"Lake Taylor",
              "facility_kind":"","fcodes":[],"largest":150000,"count":2,"buildings":[]}
        self.assertEqual(app.triage_status(site,cv),"REVIEW")
        self.assertIn("manual HVAC review",app.hit_text(cv,site))
        self.assertEqual(app.triage_status(dict(site,territory="chesapeake"),cv),"REVIEW")
        self.assertEqual(app.triage_status(dict(site,territory="hampton"),cv),"REVIEW")
        self.assertEqual(app.triage_status(dict(site,territory="suffolk",facility="Sentara Obici Hospital"),cv),"REVIEW")
        self.assertEqual(app.triage_status(dict(site,territory="portsmouth",facility="Maryview Hospital"),cv),"REVIEW")
        self.assertEqual(app.triage_status(dict(site,territory="virginia_beach"),cv),"QUIET")
        self.assertEqual(app.triage_status(dict(site,largest=99999),cv),"QUIET")

    def test_124_freemason_acceptable_review_is_not_overfit_away(self):
        z={"territory":"norfolk","land":"COMMERCIAL","largest":45090,"psq":30516,
           "count":1,"buildings":[]}
        package=detection("LARGE_PACKAGED_HVAC",.8121,.5605,43.75,34.06,bd=0,pd=3.99,kind="overview")
        chiller=detection("AIR_COOLED_CHILLER",.5499,.2007,30.39,30.03,bd=0,pd=0,kind="overview")
        cv={"detections":[package,chiller],"raw_detections":[package,chiller]}
        self.assertEqual(app.triage_status(z,cv),"REVIEW")

    def test_known_package_context_cases(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        self.assertTrue(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.869,.781,37.46,21.59,bd=54.76)))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.621,.40,56.86,21.33,bd=19,kind="overview",seam=True)))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.613,.40,57.59,40.43,bd=170.67,kind="overview")))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.749,.60,107,59,bd=11,kind="overview")))
        self.assertTrue(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.973,.785,117.9,48.8,bd=10,kind="overview")))

    def test_wide_view_loading_clutter_and_weak_singletons_are_quiet(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        dean=detection("LARGE_PACKAGED_HVAC",.9251,.8962,61.08,30.99,bd=28.36,kind="overview")
        bayne=detection("LARGE_PACKAGED_HVAC",.4538,.2354,39.19,24.63,bd=25.61,kind="overview")
        storage=detection("LARGE_PACKAGED_HVAC",.4557,.2583,47.21,44.46,bd=10.71,pd=11,kind="parcel_tile")
        for d in (dean,bayne,storage):
            self.assertFalse(app.package_rankable(z,d))
            self.assertEqual(app.triage_status(z,{"detections":[d]}),"QUIET")

    def test_777_single_credible_package_is_review(self):
        z={"land":"INDUSTRIAL","buildings":[],"largest":21221}
        ahu=detection("LARGE_PACKAGED_HVAC",.6693,.5911,26.48,23.08,kind="building")
        self.assertTrue(app.package_rankable(z,ahu))
        self.assertEqual(app.triage_status(z,{"detections":[ahu]}),"REVIEW")

    def test_484_two_seam_packages_need_nonseam_corroboration_and_cap_at_review(self):
        z={"land":"OFFICE","buildings":[],"largest":21022}
        lon,lat=-76.0,36.8
        lon2,lat2=app.lonlat_offset(lon,lat,25,0)
        a=detection("LARGE_PACKAGED_HVAC",.9369,.8839,48.12,36.35,seam=True,lon=lon,lat=lat,kind="building")
        b=detection("LARGE_PACKAGED_HVAC",.9270,.9060,41.91,20.97,seam=True,lon=lon2,lat=lat2,kind="building")
        ar_lon,ar_lat=app.lonlat_offset(lon,lat,3,0)
        br_lon,br_lat=app.lonlat_offset(lon2,lat2,3,0)
        ar=detection("LARGE_PACKAGED_HVAC",.8520,.7270,35.52,21.29,lon=ar_lon,lat=ar_lat,kind="building")
        br=detection("LARGE_PACKAGED_HVAC",.9150,.8530,49.94,39.85,lon=br_lon,lat=br_lat,kind="building")
        bare={"detections":[a,b],"raw_detections":[a,b]}
        self.assertEqual(app.triage_status(z,bare),"QUIET")
        cv={"detections":[a,b],"raw_detections":[a,b,ar,br]}
        self.assertEqual(len(app.packaged_bands(cv,z)[0]),2)
        self.assertEqual(app.triage_status(z,cv),"REVIEW")
        self.assertIn("Pkg seam-corroborated 2",app.hit_text(cv,z))

    def test_known_thermal_context_cases(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        self.assertFalse(app.thermal_detection_rankable(z,detection("COOLING_TOWER",.464,.181,30,20,kind="overview",seam=True)))
        self.assertFalse(app.thermal_detection_rankable(z,detection("AIR_COOLED_CHILLER",.759,.597,35,22,bd=113.85,rescue=True,review=True)))
        self.assertFalse(app.thermal_detection_rankable(z,detection("COOLING_TOWER",.543,.193,20,12,bd=19,rescue=True,review=True)))
        self.assertTrue(app.thermal_detection_rankable(z,detection("COOLING_TOWER",.936,.811,25,18,bd=11.54,rescue=True,review=True)))
        self.assertTrue(app.thermal_detection_rankable(z,detection("COOLING_TOWER",.975,.937,30,20,kind="overview",seam=True)))

    def test_1609_broad_weak_debris_is_quiet_but_5580_review_survives(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        debris=detection("AIR_COOLED_CHILLER",.4564,.2607,39.15,35.88,bd=15.48,kind="building")
        self.assertFalse(app.thermal_detection_rankable(z,debris))
        self.assertEqual(app.triage_status(z,{"detections":[debris]}),"QUIET")
        crac=detection("AIR_COOLED_CHILLER",.8888,.5459,17.06,16.72,rescue=True,review=True)
        self.assertTrue(app.thermal_detection_rankable(z,crac))
        self.assertEqual(app.triage_status(z,{"detections":[crac]}),"REVIEW")

    def test_residential_condenser_rescue_and_small_site_yard_debris_are_quiet(self):
        regular={"land":"INDUSTRIAL","buildings":[],"largest":21303}
        split=detection("COOLING_TOWER",.6203,.3090,20.65,13.13,bd=7.76,
                        kind="building",rescue=True,review=True)
        self.assertFalse(app.thermal_detection_rankable(regular,split))
        self.assertEqual(app.triage_status(regular,{"detections":[split]}),"QUIET")
        tiny={"land":"INDUSTRIAL","buildings":[],"largest":6417}
        debris=[
            detection("AIR_COOLED_CHILLER",.8938,.8031,19.19,7.67,bd=100.70,rescue=True,review=True),
            detection("AIR_COOLED_CHILLER",.6988,.6021,12.43,9.93,bd=62.14,rescue=True,review=True),
            detection("AIR_COOLED_CHILLER",.6418,.5471,17.73,16.58,bd=96.58,rescue=True,review=True),
        ]
        self.assertTrue(all(not app.thermal_detection_rankable(tiny,d) for d in debris))
        self.assertEqual(app.triage_status(tiny,{"detections":debris}),"QUIET")

    def test_hobby_lobby_pattern_is_review_not_strong(self):
        z={"land":"COMMERCIAL","buildings":[],"largest":147491}
        rooftop=detection("COOLING_TOWER",.9654,.8423,27.47,24.73,kind="building_focus")
        trailer=detection("LARGE_PACKAGED_HVAC",.7137,.5988,65.04,39.59,bd=15.18,kind="parcel_tile")
        cv={"detections":[rooftop,trailer],"raw_detections":[rooftop,trailer]}
        self.assertTrue(app.thermal_detection_rankable(z,rooftop))
        self.assertTrue(app.commercial_rooftop_tower_review_only(z,rooftop))
        self.assertFalse(app.package_rankable(z,trailer,cv))
        self.assertEqual(app.triage_status(z,cv),"REVIEW")
        self.assertIn("Compact rooftop tower ambiguity 1",app.hit_text(cv,z))

    def test_nexcom_strategic_near_miss_surfaces_without_claiming_equipment(self):
        nexcom={"land":"OFFICE","facility":"NAS Oceana - NEXCOM HQ","facility_kind":"",
                "zone":"","fcodes":[],"buildings":[],"largest":39430}
        cv={"detections":[],"raw_detections":[],"stage1_proposals":1}
        self.assertTrue(app.strategic_unverified_review(nexcom,cv))
        self.assertEqual(app.triage_status(nexcom,cv),"REVIEW")
        self.assertEqual(app.hit_text(cv,nexcom),"Strategic-site unverified proposal 1")
        ordinary=dict(nexcom,facility="Ordinary Office")
        self.assertEqual(app.triage_status(ordinary,cv),"QUIET")
        self.assertEqual(app.triage_status(nexcom,dict(cv,stage1_proposals=0)),"QUIET")

    def test_small_ambiguous_public_prescreen_filters_residential_scale_miscodes(self):
        home={"land":"Public/Semi Public","zone":"","facility":"Pond Cypress Drive","facility_kind":"",
              "fcodes":[],"largest":2665,"avg":2665,"count":1,"buildings":[]}
        self.assertTrue(app.ambiguous_small_public_site(home))
        self.assertEqual(app.prescreen(home,10000),(False,"AMBIGUOUS SMALL PUBLIC PARCEL"))
        school=dict(home,facility="Small School",facility_kind="school")
        self.assertFalse(app.ambiguous_small_public_site(school))
        self.assertTrue(app.prescreen(school,10000)[0])

    def test_cross_property_duplicate_prefers_containing_parcel(self):
        lon,lat=-76.1881785,36.8930294;lon2,lat2=app.lonlat_offset(lon,lat,.42,5.91)
        wrong=detection("COOLING_TOWER",.9264,.7866,30.18,17.61,bd=43.53,pd=11.82,
                        rescue=True,review=True,lon=lon,lat=lat)
        owner=detection("COOLING_TOWER",.7965,.6976,14.47,13.92,bd=15.31,pd=0,
                        rescue=True,review=True,lon=lon2,lat=lat2)
        ring=rectangle_building()["rings"]
        a={"z":{"land":"INDUSTRIAL","buildings":[],"rings":ring,"address":"5901 THURSTON"},
           "cv":{"detections":[wrong],"raw_detections":[dict(wrong)],"retained_evidence":1},"scan_index":1}
        b={"z":{"land":"INDUSTRIAL","buildings":[],"rings":ring,"address":"5925 THURSTON"},
           "cv":{"detections":[owner],"raw_detections":[dict(owner)],"retained_evidence":1},"scan_index":2}
        self.assertEqual(app.reconcile_cross_property_detections([a,b]),1)
        self.assertEqual(app.triage_status(a["z"],a["cv"]),"QUIET")
        self.assertEqual(app.triage_status(b["z"],b["cv"]),"REVIEW")
        self.assertEqual(a["cv"]["cross_property_rejected_detections"][0]["assigned_to_address"],"5925 THURSTON")
        self.assertEqual(len(a["cv"]["raw_detections"]),1)

    def test_cross_property_rule_does_not_merge_separate_or_campus_evidence(self):
        a=detection("COOLING_TOWER",.90,.70,14,12,lon=-76.0,lat=36.8)
        lon,lat=app.lonlat_offset(-76.0,36.8,18,0)
        b=detection("AIR_COOLED_CHILLER",.90,.70,14,12,lon=lon,lat=lat)
        self.assertFalse(app.cross_property_same_machine(a,b))
        b["lon"],b["lat"]=a["lon"],a["lat"];b["attribution_scope"]="CAMPUS ADJACENT"
        self.assertFalse(app.cross_property_same_machine(a,b))

    def test_context_rejected_thermal_is_quiet_and_auditable(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        d=detection("COOLING_TOWER",.464,.181,30,20,kind="overview",seam=True)
        cv={"detections":[d],"attribution_rejected":0}
        self.assertEqual(app.triage_status(z,cv),"QUIET")
        self.assertIn("Thermal context-rejected 1",app.hit_text(cv,z))

    def test_cross_class_same_machine_fuses(self):
        eng=app.LocalCV.__new__(app.LocalCV);lon,lat=-76.0,36.8
        a={"lon":lon,"lat":lat,"width_ft":20,"height_ft":20,"long_ft":20,"type":"COOLING_TOWER","image":"B01.jpg"}
        blon,blat=app.lonlat_offset(lon,lat,9,0)
        b={"lon":blon,"lat":blat,"width_ft":14,"height_ft":14,"long_ft":14,"type":"AIR_COOLED_CHILLER","image":"B01.jpg"}
        self.assertTrue(eng._same_physical(a,b,lon,lat))

    def test_storage_morphology_filters_but_protects_military(self):
        bs=[rectangle_building(lon=-76+i*.00001) for i in range(10)]
        base={"land":"COMMERCIAL","zone":"","facility":"","facility_kind":"","fcodes":[],
              "largest":2000,"avg":2000,"count":10,"buildings":bs}
        self.assertTrue(app.repetitive_storage_like(base))
        self.assertTrue(app.repetitive_storage_like(dict(base,land="INDUSTRIAL")))
        protected=dict(base,land="MILITARY")
        self.assertFalse(app.repetitive_storage_like(protected))


if __name__=="__main__":unittest.main()
