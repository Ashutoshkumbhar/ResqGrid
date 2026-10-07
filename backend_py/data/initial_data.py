from typing import List, Dict, Any

DISTRICT_METADATA = {
    "districtId": "DIST_PUNE_01",
    "districtName": "Pune District — Mula-Pawana-Mutha Basin",
    "state": "Maharashtra",
    "center": [18.5780, 73.7950],
    "zoom": 13,
    "riverSystems": ["Mula River", "Pawana River", "Mutha River"],
    "monitoredAreaSqKm": 85.4
}

INITIAL_SETTLEMENTS: List[Dict[str, Any]] = [
    {
        "id": "S1",
        "name": "Village A (Wakad Khurd)",
        "latitude": 18.5987,
        "longitude": 73.7645,
        "population": 2140,
        "elderly": 390,
        "pregnant": 120,
        "disabled": 180,
        "patients": 90,
        "vulnerablePopulation": 780,
        "elevation": 42.0,  # low-lying river bend
        "rainfall": 45.0,
        "waterLevel": "NORMAL",
        "waterLevelMeters": 1.1,
        "riskScore": 62,
        "riskStatus": "HIGH",
        "accessibility": "OPEN",
        "groundReportsCount": 1,
        "responsePriority": 78,
        "priorityRank": 2,
        "whyExplanation": [
            "Low-lying river bend terrain (42m elevation)",
            "Moderate rainfall accumulation (45mm)",
            "1 citizen waterlogging report near causeway",
            "Direct road access via R12 is currently open"
        ],
        "isSimulated": False
    },
    {
        "id": "S2",
        "name": "Village B (Sangvi Riverside)",
        "latitude": 18.5724,
        "longitude": 73.8168,
        "population": 1850,
        "elderly": 420,
        "pregnant": 145,
        "disabled": 210,
        "patients": 110,
        "vulnerablePopulation": 885,
        "elevation": 38.0,  # deepest vulnerable depression
        "rainfall": 72.0,
        "waterLevel": "WARNING",
        "waterLevelMeters": 1.7,
        "riskScore": 82,
        "riskStatus": "CRITICAL",
        "accessibility": "OPEN",
        "groundReportsCount": 2,
        "responsePriority": 92,
        "priorityRank": 1,
        "whyExplanation": [
            "Extreme low elevation (38m) at Pawana river confluence",
            "Heavy rainfall (72mm) with upstream runoff surge",
            "Water level indicator crossed WARNING threshold (1.7m)",
            "1,850 residents exposed with immediate embankment overflow risk",
            "Accessible emergency route via eastern corridor"
        ],
        "isSimulated": False
    },
    {
        "id": "S3",
        "name": "Village C (Hinjawadi Lowlands)",
        "latitude": 18.5912,
        "longitude": 73.7389,
        "population": 3420,
        "elevation": 58.0,
        "rainfall": 38.0,
        "waterLevel": "NORMAL",
        "waterLevelMeters": 0.8,
        "riskScore": 48,
        "riskStatus": "MODERATE",
        "accessibility": "OPEN",
        "groundReportsCount": 0,
        "responsePriority": 54,
        "priorityRank": 3,
        "whyExplanation": [
            "Moderate elevation (58m) with stormwater drainage capacity",
            "Rainfall within baseline manageable limits (38mm)",
            "Normal river gauge levels"
        ],
        "isSimulated": False
    },
    {
        "id": "S4",
        "name": "Village D (Baner Heights)",
        "latitude": 18.5590,
        "longitude": 73.7868,
        "population": 4100,
        "elderly": 610,
        "pregnant": 180,
        "disabled": 280,
        "patients": 140,
        "vulnerablePopulation": 1210,
        "elevation": 95.0,  # high ground relief shelter hub
        "rainfall": 30.0,
        "waterLevel": "NORMAL",
        "waterLevelMeters": 0.4,
        "riskScore": 24,
        "riskStatus": "LOW",
        "accessibility": "OPEN",
        "groundReportsCount": 0,
        "responsePriority": 20,
        "priorityRank": 5,
        "whyExplanation": [
            "High ground ridge (95m elevation), zero flood stagnation risk",
            "Designated relief assembly and medical staging point"
        ],
        "isSimulated": False
    },
    {
        "id": "S5",
        "name": "Village E (Dapodi Confluence)",
        "latitude": 18.5830,
        "longitude": 73.8340,
        "population": 1650,
        "elderly": 310,
        "pregnant": 100,
        "disabled": 170,
        "patients": 80,
        "vulnerablePopulation": 660,
        "elevation": 45.0,
        "rainfall": 52.0,
        "waterLevel": "NORMAL",
        "waterLevelMeters": 1.3,
        "riskScore": 58,
        "riskStatus": "MODERATE",
        "accessibility": "OPEN",
        "groundReportsCount": 1,
        "responsePriority": 64,
        "priorityRank": 4,
        "whyExplanation": [
            "River junction proximity with rising tributary backflow",
            "1 localized drainage choke report logged"
        ],
        "isSimulated": False
    }
]

INITIAL_ROADS: List[Dict[str, Any]] = [
    {
        "id": "R12",
        "name": "Wakad Bridge Causeway (R12)",
        "source": "Hinjawadi Base",
        "destination": "Village A (Wakad)",
        "status": "OPEN",
        "distanceKm": 4.2,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5880, 73.7550],
            [18.5925, 73.7590],
            [18.5960, 73.7620],
            [18.5987, 73.7645]
        ]
    },
    {
        "id": "R1",
        "name": "NH-48 Western Bypass Link (R1)",
        "source": "Hinjawadi Base",
        "destination": "Baner Heights (S4)",
        "status": "OPEN",
        "distanceKm": 5.8,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5880, 73.7550],
            [18.5770, 73.7660],
            [18.5660, 73.7760],
            [18.5590, 73.7868]
        ]
    },
    {
        "id": "R2",
        "name": "Baner-Sangvi Elevated Corridor (R2)",
        "source": "Baner Heights (S4)",
        "destination": "Village B (Sangvi)",
        "status": "OPEN",
        "distanceKm": 4.6,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5590, 73.7868],
            [18.5650, 73.7990],
            [18.5690, 73.8080],
            [18.5724, 73.8168]
        ]
    },
    {
        "id": "R3",
        "name": "Sangvi-Dapodi Rivergate Road (R3)",
        "source": "Village B (Sangvi)",
        "destination": "Village E (Dapodi)",
        "status": "OPEN",
        "distanceKm": 2.4,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5724, 73.8168],
            [18.5770, 73.8240],
            [18.5830, 73.8340]
        ]
    },
    {
        "id": "R4",
        "name": "Wakad-Sangvi Secondary Link (R4)",
        "source": "Village A (Wakad)",
        "destination": "Village B (Sangvi)",
        "status": "OPEN",
        "distanceKm": 5.1,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5987, 73.7645],
            [18.5890, 73.7820],
            [18.5790, 73.8020],
            [18.5724, 73.8168]
        ]
    },
    {
        "id": "R7",
        "name": "Baner North High-Ridge Bypass (R7 - Alternative Route)",
        "source": "Hinjawadi Base",
        "destination": "Village A (Wakad)",
        "status": "OPEN",
        "distanceKm": 7.4,
        "accessibility": "NORMAL",
        "coordinates": [
            [18.5880, 73.7550],
            [18.5800, 73.7600],
            [18.5750, 73.7720],
            [18.5850, 73.7800],
            [18.5950, 73.7750],
            [18.5987, 73.7645]
        ]
    }
]

INITIAL_RESOURCES: List[Dict[str, Any]] = [
    {
        "id": "BOAT-02",
        "type": "RESCUE_BOAT",
        "name": "Rescue Boat 02",
        "icon": "Ship",
        "locationName": "Hinjawadi Marine Rescue Post",
        "latitude": 18.5880,
        "longitude": 73.7550,
        "status": "AVAILABLE",
        "speedKmh": 35.0,
        "currentAssignment": None
    },
    {
        "id": "AMB-01",
        "type": "AMBULANCE",
        "name": "Ambulance 01",
        "icon": "Ambulance",
        "locationName": "Baner Emergency Base",
        "latitude": 18.5620,
        "longitude": 73.7780,
        "status": "AVAILABLE",
        "speedKmh": 50.0,
        "currentAssignment": None
    },
    {
        "id": "TEAM-03",
        "type": "RESCUE_TEAM",
        "name": "Rescue Team 03 (NDRF Unit)",
        "icon": "ShieldAlert",
        "locationName": "Dapodi Fire & Rescue HQ",
        "latitude": 18.5710,
        "longitude": 73.8290,
        "status": "AVAILABLE",
        "speedKmh": 45.0,
        "currentAssignment": None
    },
    {
        "id": "HOSP-01",
        "type": "HOSPITAL",
        "name": "District Multi-Specialty Hospital 01",
        "icon": "Building2",
        "locationName": "Baner Medical Enclave",
        "latitude": 18.5550,
        "longitude": 73.8050,
        "status": "AVAILABLE",
        "speedKmh": 0.0,
        "currentAssignment": None
    },
    {
        "id": "SHELTER-01",
        "type": "SHELTER",
        "name": "High-Ground Community Shelter 01",
        "icon": "Home",
        "locationName": "Baner Hilltop Center (Cap: 600)",
        "latitude": 18.5610,
        "longitude": 73.7890,
        "status": "AVAILABLE",
        "speedKmh": 0.0,
        "currentAssignment": None
    }
]

INITIAL_REPORTS: List[Dict[str, Any]] = [
    {
        "id": "REP-101",
        "location": "Village B (Sangvi Riverside)",
        "description": "Pawana river embankment water encroaching onto market perimeter; ground floor shops submerged 0.5m.",
        "severity": "HIGH",
        "reporterType": "WARD_OFFICER",
        "timestamp": "10 minutes ago",
        "status": "VERIFIED_AI",
        "extractedInfo": {
            "location": "Village B (Sangvi)",
            "severity": "HIGH",
            "roadStatus": "AT_RISK",
            "infrastructure": "River Embankment",
            "confidence": 0.94
        }
    },
    {
        "id": "REP-102",
        "location": "Village A (Wakad)",
        "description": "Drainage overflow near bus terminus; slight water accumulation on service lane.",
        "severity": "MODERATE",
        "reporterType": "CITIZEN",
        "timestamp": "25 minutes ago",
        "status": "VERIFIED_AI",
        "extractedInfo": {
            "location": "Village A (Wakad)",
            "severity": "MODERATE",
            "roadStatus": "OPEN",
            "infrastructure": "Drainage Grid",
            "confidence": 0.88
        }
    }
]
