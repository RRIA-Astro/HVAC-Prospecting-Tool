"""Jurisdiction data adapters. No detector or prospect-ranking rules live here.

Norfolk sources were verified on 2026-09-18. Chesapeake sources, Newport News,
Hampton sources, and the statewide VGIN orthophoto service were verified on 2026-09-20.
Keep raw assessment classifications separate from the normalized detector context.
"""
import re


PROFILES = {
    "virginia_beach": {
        "key": "virginia_beach", "name": "Virginia Beach",
        "default_address": "717 General Booth Blvd", "default_radius": "1.0",
        "address": "https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/0/query",
        "parcel": "https://geo.vbgov.com/mapservices/rest/services/Business_Systems/Pictometry_Online/MapServer/4/query",
        "parcel_fields": "PAR_GPIN,FULL_ADDR,PROP_ADDRESS,LAND_USE,ZONING,PROP_CLASS,LATITUDE,LONGITUDE",
        "building": "https://geo.vbgov.com/mapservices/rest/services/Basemaps/Structures_and_Physical_Features/MapServer/6/query",
        "building_source": "VB CITY", "building_where": "1=1",
        "fallback_building": "https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query",
        "imagery": "https://geo.vbgov.com/imageservices/rest/services/Imagery/Aerial2025/ImageServer/exportImage",
        "imagery_kind": "image_server", "imagery_label": "Virginia Beach aerial 2025",
        "assessment": "", "assessment_label": "Virginia Beach parcel attributes",
        "query_chunk": 1800, "require_buildings": False,
    },
    "norfolk": {
        "key": "norfolk", "name": "Norfolk",
        "default_address": "800 E City Hall Ave", "default_radius": "0.5",
        "address": "https://gisshare.norfolk.gov/pubserver/rest/services/OpenData/Parcels/FeatureServer/0/query",
        "parcel": "https://gisshare.norfolk.gov/pubserver/rest/services/OpenData/Parcels/FeatureServer/1/query",
        "parcel_fields": "OBJECTID,GPIN,TAX_ACCT,LRSN",
        "building": "https://gisshare.norfolk.gov/server/rest/services/NORFOLKAIR/AIR_Basemap/MapServer/34/query",
        "building_source": "NORFOLK CITY",
        "building_where": "(DEMO = 0 OR DEMO IS NULL) AND (FTR_CODE IS NULL OR FTR_CODE IN (2000,2010,2020,2021,2022,2023,2024,2025,2026,2030,2040,2070,2080))",
        "fallback_building": "https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query",
        "imagery": "https://gisshare.norfolk.gov/pubserver/rest/services/AerialPhotos/2025/MapServer/export",
        "imagery_kind": "map_server", "imagery_label": "Norfolk aerial 2025",
        "assessment": "https://data.norfolk.gov/resource/qva7-tzrf.json",
        "assessment_label": "Norfolk Property Assessment and Sales FY27",
        "query_chunk": 1000, "require_buildings": True,
    },
    "chesapeake": {
        "key": "chesapeake", "name": "Chesapeake",
        "enabled": False,
        "default_address": "306 Cedar Rd", "default_radius": "1.0",
        "address": "https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/1/query",
        "parcel": "https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/15/query",
        "parcel_fields": "OBJECTID,CALCACREAGE,PARNO,MAP_PARCEL,CNTRL_NO,ADDRESS,ADDRESSZIP,UNIT,PROJECT,PROPCLASS,ASSESSMNT_DIST",
        "building": "https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/4/query",
        "building_source": "CHESAPEAKE CITY", "building_where": "1=1",
        "fallback_building": "https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query",
        "imagery": "https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VBMP_Imagery/MostRecentImagery_WGS/MapServer/export",
        "imagery_kind": "map_server", "imagery_label": "VGIN VBMP most-recent imagery (2022/2023/2025)",
        "assessment": "https://gis.cityofchesapeake.net/mapping/rest/services/OpenData/OpenData/MapServer/30/query",
        "assessment_label": "Chesapeake Real Estate Parcel Class",
        "query_chunk": 1800, "require_buildings": True,
    },
    "newport_news": {
        "key": "newport_news", "name": "Newport News",
        "enabled": False,
        "default_address": "500 J Clyde Morris Blvd", "default_radius": "0.5",
        "address": "https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/0/query",
        "parcel": "https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/6/query",
        "parcel_fields": "OBJECTID,PARCELID,SITEADDRESS,PRPRTYDSCRP,USECD,USEDSCRP,CLASSCD,CLASSDSCRP,OWNERNME1,ZONE,VACANT,ASMT_LANDUSE,LATITUDE,LONGITUDE",
        "building": "https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/11/query",
        "building_source": "NEWPORT NEWS CITY", "building_where": "1=1",
        "fallback_building": "https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query",
        "imagery": "https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VBMP_Imagery/MostRecentImagery_WGS/MapServer/export",
        "imagery_kind": "map_server", "imagery_label": "VGIN VBMP most-recent imagery (2022/2023/2025)",
        "assessment": "https://maps.nnva.gov/arcgis/rest/services/Operational/EnerGov/MapServer/6/query",
        "assessment_label": "Newport News EnerGov parcel assessment",
        "query_chunk": 2000, "require_buildings": True,
    },
    "hampton": {
        "key": "hampton", "name": "Hampton",
        "default_address": "3000 Coliseum Dr", "default_radius": "0.5",
        "address": "https://webgis3.hampton.gov/server/rest/services/Layers/MapServer/1/query",
        "parcel": "https://webgis3.hampton.gov/server/rest/services/Layers/MapServer/0/query",
        "parcel_fields": "OBJECTID,P_TYPE,LRSNTXT,LRSNINT,GPIN,SITUS,SQFT,ACREAGE",
        "building": "https://webgis3.hampton.gov/server/rest/services/Web/CQ_Int1/MapServer/0/query",
        "building_source": "HAMPTON CITY",
        "building_where": "S_TYPE IN (1810,1820,1840,1850)",
        "fallback_building": "https://dsfmportal.dcr.virginia.gov/server/rest/services/CivilReference/Civil_Reference_Layers/MapServer/2/query",
        "imagery": "https://webgis3.hampton.gov/server/rest/services/Aerials_2026/MapServer/export",
        "imagery_kind": "map_server", "imagery_layers": "show:13",
        "imagery_label": "Hampton municipal aerial 2026",
        "assessment": "https://webgis3.hampton.gov/server/rest/services/Web/CQ_RealEstate_Tables/MapServer/3/query",
        "assessment_label": "Hampton Real Estate improvements",
        "query_chunk": 2000, "require_buildings": True,
    },
}

ASSESSMENT_FIELDS = (
    "gpin", "lrsn", "extension", "property_use", "property_class_description",
    "property_street_number", "property_street_number_suffix", "property_street_direction",
    "property_street_name", "property_street_type", "property_street_suffix", "unit_number",
)

# Public Norfolk WS7_FEATURE_CODE domain. Building type supplements assessment
# context; the combined commercial/industrial code must NOT label every office
# industrial. Water towers and storage tanks are not building footprints.
NORFOLK_BUILDING_CONTEXT = {
    2000: "RESIDENTIAL BUILDING", 2010: "COMMERCIAL BUILDING",
    2020: "INSTITUTIONAL BUILDING", 2021: "SCHOOL", 2022: "UNIVERSITY",
    2023: "HOSPITAL", 2024: "GOVERNMENT LIBRARY", 2025: "GOVERNMENT RECREATION CENTER",
    2026: "GOVERNMENT PUBLIC SAFETY", 2030: "GARAGE", 2040: "COMMERCIAL RAIL STATION",
    2070: "OTHER BUILDING", 2080: "BUILDING UNDER CONSTRUCTION",
}

# Chesapeake OpenData Building Outlines BUILDINGCLASS coded-value domain. The
# city's class 1 is explicitly "General/Residential"; call it GENERAL here so
# an otherwise commercial parcel is not rejected as residential merely because
# its footprint was not assigned a more specific class.
CHESAPEAKE_BUILDING_CONTEXT = {
    1: "GENERAL BUILDING", 2: "GOVERNMENT", 3: "MEDICAL", 4: "EDUCATION SCHOOL",
    5: "TRANSPORTATION", 6: "COMMERCIAL", 7: "RELIGIOUS", 8: "RECREATION",
    9: "CULTURAL HERITAGE", 10: "HOSPITALITY HOTEL", 11: "AIRPORT",
    12: "INDUSTRIAL", 13: "COMMUNITY CENTER", 14: "APARTMENT",
}

# Newport News EnerGov Building Detail FEATURECODE domain.
NEWPORT_NEWS_BUILDING_CONTEXT = {
    "1": "RESIDENTIAL BUILDING", "2": "COMMERCIAL BUILDING",
    "3": "PUBLIC BUILDING", "4": "MISCELLANEOUS STRUCTURE",
}

# Hampton CQ Buildings S_TYPE domain. Pools, tanks, towers, and sheds are
# deliberately excluded by the profile query because they are not building
# footprints and must not inflate the prescreen's building-size context.
HAMPTON_BUILDING_CONTEXT = {
    1810: "NONRESIDENTIAL BUILDING", 1820: "RESIDENTIAL BUILDING",
    1840: "TRAILER HOME", 1850: "GARAGE",
}


def get_profile(key="virginia_beach"):
    if key not in PROFILES:
        raise ValueError(f"Unsupported territory: {key!r}. Select Hampton, Norfolk, or Virginia Beach.")
    return PROFILES[key]


def numeric_id(value):
    """Reconcile ArcGIS text GPINs with Socrata numeric GPINs without rounding."""
    value = str(value if value is not None else "").strip()
    if not re.fullmatch(r"\d+(?:\.0+)?", value):
        return ""
    return str(int(value.split(".")[0]))


STREET_TYPES = {
    "AV": "AVE", "AVENUE": "AVE", "STREET": "ST", "ROAD": "RD",
    "BOULEVARD": "BLVD", "DRIVE": "DR", "COURT": "CT", "CIRCLE": "CIR",
    "LANE": "LN", "PLACE": "PL", "PARKWAY": "PKWY", "TERRACE": "TER",
    "HIGHWAY": "HWY", "TRAIL": "TRL", "WAY": "WAY", "SQUARE": "SQ",
}
DIRECTIONS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}


def canonical_address(text):
    text = text.split(",", 1)[0].upper().strip()
    text = re.sub(r"\s+(?:HAMPTON|NORFOLK|NEWPORT NEWS|VIRGINIA BEACH|CHESAPEAKE)(?:\s+VA(?:\s+\d{5})?)?$", "", text)
    words = re.sub(r"[.\s]+", " ", text).strip().split()
    return " ".join(STREET_TYPES.get(w, DIRECTIONS.get(w, w)) for w in words)


def norfolk_address_where(text):
    normalized = canonical_address(text)
    match = re.fullmatch(r"(\d+)\s+(.+)", normalized)
    if not match:
        raise ValueError("Enter a Norfolk street address, including its house number.")
    number, street = match.groups()
    words = street.split()
    pre = words.pop(0) if words[0] in ("N", "S", "E", "W", "NE", "NW", "SE", "SW") else ""
    # A street named 'Park' is not a suffix. Only remove recognized types.
    known_types = set(STREET_TYPES.values()) | {"AVE", "ST", "RD", "BLVD", "DR", "CT", "CIR", "LN", "PL", "PKWY", "TER", "HWY", "TRL", "SQ"}
    if words and words[-1] in known_types:
        words.pop()
    if not words:
        raise ValueError("Enter the street name as well as its house number.")
    name = " ".join(words).replace("'", "''")
    where = f"HSE_NUM = {int(number)} AND UPPER(ST_NAME) = '{name}'"
    if pre:
        where += f" AND UPPER(PRE_DIR) = '{pre}'"
    return where


def chesapeake_address_where(text):
    """Match the city's normalized full-address field without loose substring geocoding."""
    normalized = canonical_address(text)
    if not re.fullmatch(r"\d+\s+.+", normalized):
        raise ValueError("Enter a Chesapeake street address, including its house number.")
    return "UPPER(ADDRESS) LIKE '" + normalized.replace("'", "''") + "%'"


def newport_news_address_where(text):
    """Match Newport News EnerGov base addresses while allowing unit-address records."""
    normalized = canonical_address(text)
    if not re.fullmatch(r"\d+\s+.+", normalized):
        raise ValueError("Enter a Newport News street address, including its house number.")
    return "UPPER(FULLADDR) LIKE '" + normalized.replace("'", "''") + "%'"


def hampton_address_where(text):
    """Match Hampton's official full-address field while allowing unit records."""
    normalized = canonical_address(text)
    if not re.fullmatch(r"\d+\s+.+", normalized):
        raise ValueError("Enter a Hampton street address, including its house number.")
    return "UPPER(FullAdd) LIKE '" + normalized.replace("'", "''") + "%'"


def chesapeake_land_use(attributes, classes):
    """Return auditable Chesapeake parcel-class context for existing prescreen rules."""
    code = str(attributes.get("PROPCLASS") or "").strip()
    description = str(classes.get(code) or "").strip().upper()
    if not description:
        description = "UNKNOWN PROPERTY CLASS" + ((" " + code) if code else "")
    project = str(attributes.get("PROJECT") or "").strip().upper()
    return " | ".join(x for x in (description, project) if x)


def newport_news_land_use(attributes):
    """Normalize auditable EnerGov assessment fields for the shared prescreen rules."""
    values=[]
    for field in ("ASMT_LANDUSE", "USEDSCRP", "CLASSDSCRP"):
        value=" ".join(str(attributes.get(field) or "").upper().split())
        if value and value not in values:values.append(value)
    if str(attributes.get("VACANT") or "").strip().upper()=="Y" and "VACANT LAND" not in values:
        values.append("VACANT LAND")
    return " | ".join(values) or "UNKNOWN"


def hampton_land_use(rows):
    """Prefer active nonresidential improvements while preserving campus variety.

    Hampton's assessment table can contain dozens of improvements on one campus.
    A residential dormitory must not erase a hospital, college, laboratory, or
    other valuable commercial improvement on the same official parcel.
    """
    active=[r for r in rows if str(r.get("ImpStat") or "").strip().upper() in ("", "A")]
    nonres=[r for r in active if str(r.get("ImprType") or "").strip().upper() not in ("DWELLING", "RESIDENTIAL")]
    chosen=nonres or active
    values=[]
    for row in chosen:
        value=" ".join(str(row.get("UseDesc") or row.get("UseCode") or row.get("BldgType") or row.get("ImprType") or "").upper().split())
        if value and value not in values:values.append(value)
    return " | ".join(values) or "UNKNOWN"


def assessment_address(row):
    number = numeric_id(row.get("property_street_number"))
    number += str(row.get("property_street_number_suffix") or "").strip()
    parts = [number] + [str(row.get(k) or "").strip() for k in (
        "property_street_direction", "property_street_name", "property_street_type", "property_street_suffix")]
    return " ".join(x for x in parts if x).strip()


# These are Norfolk assessment classes, not Virginia Beach land-use codes.
# Exact classifications are retained in scan audit fields; these labels feed the
# existing prescreen and rescue rules, which expect descriptive context.
CLASS_CONTEXT = {
    408: "COMMERCIAL RETIREMENT HOME", 409: "COMMERCIAL ROOMING HOUSE",
    410: "MOTEL", 411: "HOTEL", 412: "MEDICAL HOSPITAL NURSING HOME",
    413: "MEDICAL HOSPITAL", 414: "MEDICAL HOSPITAL",
    415: "MULTI FAMILY MOBILE HOME PARK", 417: "COMMERCIAL DAY CARE",
    418: "COMMERCIAL MIXED USE RETAIL", 419: "COMMERCIAL OTHER HOUSING",
    420: "RETAIL", 421: "RETAIL SUPERMARKET", 422: "RETAIL DEPARTMENT STORE",
    423: "COMMERCIAL", 425: "RETAIL SHOPPING CENTER", 426: "RETAIL SHOPPING CENTER",
    427: "RETAIL SHOPPING CENTER", 428: "RETAIL CONVENIENCE STORE", 429: "RETAIL",
    430: "RESTAURANT", 431: "RESTAURANT BAR", 435: "RESTAURANT",
    436: "RESTAURANT", 437: "RETAIL PHARMACY", 438: "RETAIL CONVENIENCE STORE",
    439: "RESTAURANT FOOD SERVICE", 442: "MEDICAL CLINIC OFFICE",
    443: "MEDICAL DENTAL CLINIC", 446: "MEDICAL VETERINARY CLINIC",
    447: "OFFICE", 448: "OFFICE", 449: "OFFICE",
    # A commercial condominium is a legal ownership form, not residential use.
    450: "COMMERCIAL UNIT", 454: "COMMERCIAL AUTO SALES SERVICE",
    477: "SCHOOL", 480: "WAREHOUSE", 482: "DISTRIBUTION TRUCK TERMINAL",
    485: "SELF STORAGE", 487: "COMMERCIAL RADIO TELEVISION STATION",
    601: "FEDERAL GOVERNMENT", 602: "MULTI FAMILY FEDERAL RESIDENTIAL",
    603: "UNIVERSITY ODU VACANT LAND", 604: "UNIVERSITY NSU VACANT LAND",
    606: "GOVERNMENT", 607: "UNIVERSITY ODU", 608: "UNIVERSITY NSU",
    609: "INDUSTRIAL PORT AUTHORITY", 611: "GOVERNMENT",
    612: "MULTI FAMILY MUNICIPAL RESIDENTIAL", 613: "SCHOOL",
    615: "GOVERNMENT PARK", 616: "UTILITY SOLID WASTE",
    617: "GOVERNMENT MUSEUM", 618: "UTILITY WATER DISTRIBUTION",
    619: "GOVERNMENT LIBRARY", 621: "GOVERNMENT HOUSING AUTHORITY",
    622: "MULTI FAMILY HOUSING AUTHORITY RESIDENTIAL", 624: "UTILITY",
    627: "GOVERNMENT ECONOMIC DEVELOPMENT", 629: "INDUSTRIAL DEVELOPMENT AUTHORITY",
    635: "GOVERNMENT PARK", 636: "GOVERNMENT AIRPORT",
    641: "GOVERNMENT", 643: "UTILITY PUMP STATION", 644: "UTILITY",
    653: "MULTI FAMILY UTILITY RESIDENTIAL", 656: "UTILITY SOLID WASTE",
    667: "MEDICAL HEALTH CARE", 671: "CHURCH",
    672: "SINGLE FAMILY RELIGIOUS RESIDENCE", 673: "SCHOOL RELIGIOUS EDUCATION",
    674: "CHURCH", 675: "CHURCH AUXILIARY", 676: "MEDICAL ASSISTED LIVING",
    678: "COMMERCIAL YMCA YWCA", 691: "PUBLIC/SEMI PUBLIC",
    692: "MULTI FAMILY HOA", 693: "SCHOOL EDUCATION", 695: "MEDICAL HEALTH CARE",
}


def norfolk_land_use(row):
    use = str(row.get("property_use") or "").strip().upper()
    description = str(row.get("property_class_description") or "").strip()
    match = re.match(r"^(\d{3})\b", description)
    code = int(match.group(1)) if match else None
    if code in CLASS_CONTEXT:
        return CLASS_CONTEXT[code]
    if use.startswith("SINGLE FAMILY") or code in range(510, 520):
        return "SINGLE FAMILY"
    if use == "DUPLEX" or code in (520, 521):
        return "DUPLEX"
    if use in ("TRIPLEX", "FOURPLEX", "CO-OP") or code in (530, 531, 540, 541, 558):
        return "MULTI FAMILY"
    if use == "APARTMENT" or code in range(401, 408):
        return "APARTMENT"
    if use in ("CONDOMINIUM", "RESIDENTIAL", "RESIDENTIAL OUTBUILDING") or code in range(547, 560) or code == 522:
        return "CONDO RESIDENTIAL" if use == "CONDOMINIUM" or code in range(547, 560) else "SINGLE FAMILY RESIDENTIAL"
    if use == "INDUSTRIAL":
        return "INDUSTRIAL"
    if use == "COMMERCIAL":
        return "COMMERCIAL"
    if use == "VACANT LAND":
        return "SINGLE FAMILY VACANT LAND" if code == 500 else "VACANT LAND"
    if use == "NON-TAXABLE":
        # Exempt does not, by itself, mean government, university, or military.
        return "VACANT LAND" if "VACANT" in description.upper() else "UNKNOWN EXEMPT USE"
    return "UNKNOWN"


def assessment_choice(rows):
    """One nonresidential improvement can qualify a mixed/campus parcel.

    Do not let a vacant-land extension or residential auxiliary dwelling erase
    an assessed hospital/university/industrial building. Do not combine all
    raw descriptions into context (commercial condos would become residential).
    """
    def key(row):
        land = norfolk_land_use(row)
        residential = any(k in land for k in ("SINGLE FAMILY", "DUPLEX", "MULTI FAMILY", "APARTMENT", "CONDO"))
        vacant = "VACANT" in str(row.get("property_class_description") or "").upper() or str(row.get("property_use") or "").upper() == "VACANT LAND"
        unknown = land.startswith("UNKNOWN")
        priority = any(k in land for k in ("HOSP", "MEDICAL", "UNIVERS", "INDUSTR", "UTILITY", "GOVERN", "SCHOOL", "WAREHOUSE", "DISTRIBUT"))
        quality = 3 if vacant else 4 if unknown else 2 if residential else 0 if priority else 1
        extension = str(row.get("extension") or "").upper()
        # L00 describes land/ownership. For example, publicly owned land can
        # carry a hotel or apartment C01 improvement; use the building's class.
        improvement = bool(re.fullmatch(r"[CR]\d+", extension)) and not vacant
        return 0 if improvement else 1, quality, extension, assessment_address(row), str(row.get("property_class_description") or "")
    return min(rows, key=key) if rows else None


def source_metadata(key="virginia_beach"):
    p = get_profile(key)
    return {"territory": key, "city": p["name"], "address_service": p["address"],
            "parcel_service": p["parcel"], "building_service": p["building"],
            "fallback_building_service": p["fallback_building"],
            "imagery_service": p["imagery"], "imagery_source": p["imagery_label"],
            "assessment_service": p["assessment"], "assessment_source": p["assessment_label"]}
