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


class V0116LogicTests(unittest.TestCase):
    def test_frozen_primary_operating_points(self):
        self.assertEqual(app.APP_VERSION,"0.11.6")
        self.assertEqual((app.CANDIDATE_THRESHOLD,app.TOWER_CHILLER_THRESHOLD,app.LARGE_PACKAGED_THRESHOLD),(.07,.35,.45))

    def test_5925_target_is_well_inside_a_zoom_crop(self):
        origins=app.LocalCV.__new__(app.LocalCV).perimeter_rescue_tile_origins(1800,1800)
        # Original-image coordinates of the side-yard fan bank in F02_138944sf.jpg.
        x,y=1535,935;t=app.PERIMETER_RESCUE_TILE_PX
        margins=[min(x-x0,y-y0,x0+t-x,y0+t-y) for x0,y0 in origins if x0<=x<=x0+t and y0<=y<=y0+t]
        self.assertGreaterEqual(max(margins),200)

    def test_zoom_detection_maps_back_to_source_coordinates(self):
        eng=app.LocalCV.__new__(app.LocalCV);eng.candidate=_Candidate()
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

    def test_known_package_context_cases(self):
        z={"land":"INDUSTRIAL","buildings":[]}
        self.assertTrue(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.869,.781,37.46,21.59,bd=54.76)))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.621,.40,56.86,21.33,bd=19,kind="overview",seam=True)))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.613,.40,57.59,40.43,bd=170.67,kind="overview")))
        self.assertFalse(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.749,.60,107,59,bd=11,kind="overview")))
        self.assertTrue(app.package_rankable(z,detection("LARGE_PACKAGED_HVAC",.973,.785,117.9,48.8,bd=10,kind="overview")))

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
