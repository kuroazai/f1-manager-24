from enum import IntEnum


class PerformanceStatTypes(IntEnum):
    CHASSIS = 0
    FRONT_WING_AND_NOSE = 1
    CORNERING = 2
    BRAKING = 3
    CONTROL = 4
    SMOOTHNESS = 5
    ADAPTABILITY = 6
    OVERTAKING = 7
    DEFENCE = 8
    ACCELERATION = 9
    ACCURACY = 10
    TRAINING = 11
    PIT_CREW_MANAGEMENT = 12
    FRIENDLINESS = 13
    REAR_WING = 14
    SIDE_PODS = 15
    FLOOR_AND_DIFFUSER = 16
    SUSPENSION = 17
    ROLL_REDUCTION = 18
    COOLING = 19
    DRS = 20
    IMPROVED_DEVELOPMENT = 21
    APTITUDE = 22
    LEADERSHIP = 23
    PROCESSES = 24
    FEEDBACK = 25
    HIGH_SPEED_DOWNFORCE = 26
    MEDIUM_SPEED_DOWNFORCE = 27
    LOW_SPEED_DOWNFORCE = 28
    DRAG = 29
    AIRFLOW_MANAGEMENT = 30
    SENSITIVITY = 31
    FRONT_AND_REAR_JACKS = 32
    TYRES = 33
    WING_ADJUSTMENT_AND_REPLACEMENT = 34
    CAR_RELEASE = 35
    SPEED = 36
    CONSISTENCY = 37
    FATIGUE = 38
    CAR_SETUP = 39
    WHEEL_GUN = 40
    WHEEL_OFF = 41
    WHEEL_ON = 42
    COMPOSURE = 43


class BuildingEnumsTypes(IntEnum):
    WEATHER_CENTRE = 1
    DESIGN_CENTRE = 2
    FACTORY = 3
    RACE_SIMULATOR = 4
    WIND_TUNNEL = 5
    CFD_SIMULATOR = 6
    SUSPENSION_SIMULATOR = 7
    CAR_PART_TEST_CENTRE = 8
    TEAM_HUB = 9
    HELIPAD = 10
    MEMORABILIA_ROOM = 11
    TOUR_CENTRE = 12
    HOSPITALITY_AREA = 13
    SCOUTING_DEPARTMENT = 14
    BOARD_ROOM = 15
    MEDICAL_BAY_UPGRADE = 16


class BuildingStates(IntEnum):
    CONSTRUCTING = 1
    OPEN = 2
    REFURBISHING = 3
    UPGRADING = 4


class PartsEnumStats(IntEnum):
    AirFlowFront = 0
    AirFlowTolerance = 1
    TyrePreservation = 2
    DRSDelta = 3
    DragReduction = 4
    EngineCooling = 5
    FuelEfficiency = 6
    LowSpeedDownforce = 7
    MedSpeedDownforce = 8
    HighSpeedDownforce = 9
    Power = 10
    DEPRECATED_PerformanceThreshold = 11
    DEPRECATED_PerformanceLoss = 12
    AirFlowMiddle = 13
    OperationalRange = 14
    Durability = 15


class DifficultyLevels(IntEnum):
    VERYEASY = 0
    EASY = 1
    MEDIUM = 2
    HARD = 3
    VERYHARD = 4


class PartsEnumType(IntEnum):
    Engine = 0
    ERS = 1
    Gearbox = 2
    Body = 3
    FrontWing = 4
    RearWing = 5
    SidePods = 6
    Floor = 7
    Suspension = 8