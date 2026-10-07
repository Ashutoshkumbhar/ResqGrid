from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ExtractedReportInfo(BaseModel):
    location: str
    severity: str
    roadStatus: str
    infrastructure: str
    confidence: float

class GroundReport(BaseModel):
    id: str
    location: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    reporterType: str  # CITIZEN, FIRST_RESPONDER, WARD_OFFICER
    timestamp: str
    status: str = "VERIFIED_AI"
    extractedInfo: Optional[ExtractedReportInfo] = None

class Settlement(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    population: int
    elderly: int = 0
    pregnant: int = 0
    disabled: int = 0
    patients: int = 0
    vulnerablePopulation: int = 0
    elevation: float  # in meters
    rainfall: float   # in mm
    waterLevel: str   # NORMAL, WARNING, CRITICAL
    waterLevelMeters: float
    riskScore: int    # 0 - 100
    riskStatus: str   # LOW, MODERATE, HIGH, CRITICAL
    accessibility: str  # OPEN, AT_RISK, CUT_OFF
    groundReportsCount: int = 0
    responsePriority: int = 0  # 0 - 100
    priorityRank: int = 1
    whyExplanation: List[str] = []
    isSimulated: bool = False

class Road(BaseModel):
    id: str
    name: str
    source: str
    destination: str
    status: str  # OPEN, AT_RISK, BLOCKED
    distanceKm: float
    accessibility: str  # NORMAL, RESTRICTED, IMPASSABLE
    coordinates: List[List[float]]  # [[lat, lng], [lat, lng], ...]

class EmergencyResource(BaseModel):
    id: str
    type: str  # AMBULANCE, RESCUE_BOAT, RESCUE_TEAM, HOSPITAL, SHELTER
    name: str
    icon: str
    locationName: str
    latitude: float
    longitude: float
    status: str  # AVAILABLE, DEPLOYED, BUSY, UNAVAILABLE
    speedKmh: float = 40.0
    currentAssignment: Optional[str] = None
    capacity: Optional[int] = None
    currentOccupancy: int = 0
    freeCapacity: Optional[int] = None

class RouteResult(BaseModel):
    routeId: str
    resourceId: str
    resourceName: str
    targetSettlementId: str
    targetSettlementName: str
    originalRouteStatus: str  # VALID, INVALID
    alternativeRouteStatus: Optional[str] = None  # VALID, NOT_NEEDED, ESCALATION_REQUIRED
    originalPath: List[str] = []
    originalCoordinates: List[List[float]] = []
    alternativePath: Optional[List[str]] = None
    alternativeCoordinates: Optional[List[List[float]]] = None
    blockedRoadsOnPath: List[str] = []
    distanceKm: float
    etaMinutes: int
    escalationRequired: bool = False
    explanation: str

class ResourceRecommendation(BaseModel):
    settlementId: str
    settlementName: str
    priorityRank: int
    priorityScore: int
    recommendedResourceId: str
    recommendedResourceName: str
    recommendedResourceType: str
    distanceKm: float
    etaMinutes: int
    routeStatus: str
    whySelected: List[str]
    confidenceScore: float

class Alert(BaseModel):
    id: str
    type: str  # CRITICAL_FLOOD_WARNING, EVACUATION_ORDER, ROAD_ISOLATION_ALERT
    title: str
    settlementId: str
    settlementName: str
    riskScore: int
    severity: str
    message: str
    evidence: List[str]
    confidence: float
    recommendedAction: str
    timestamp: str

class KPISummary(BaseModel):
    criticalAreas: int
    affectedPopulation: int
    blockedRoads: int
    activeWarnings: int
    availableResources: int
    districtName: str = "Pune District (Mula-Mutha Basin)"
    lastUpdated: str

class SimulationStatus(BaseModel):
    mode: str = "LIVE"  # LIVE, DEMO_SIMULATION, REPLAYED_DATA
    isSimulationActive: bool = False
    step: int = 1
    totalSteps: int = 6
    stepTitle: str = "Initial Baseline Situation"
    description: str = "Normal operating baseline with light precipitation"
