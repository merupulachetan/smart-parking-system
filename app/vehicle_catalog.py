"""
Comprehensive vehicle catalog for India — all types, brands, and models.
"""
from __future__ import annotations
import json
from typing import Any

CATALOG: dict[str, dict[str, Any]] = {

    # ── BIKE / MOTORCYCLE ────────────────────────────────────────────────────
    "bike": {
        "label": "Motorcycle / Bike",
        "brands": {
            "Hero": ["Splendor Plus", "Splendor+", "HF Deluxe", "Passion Pro",
                     "Glamour", "Xtreme 160R", "Xtreme 200S", "Xoom 110",
                     "Vida V1", "Vida V2"],
            "Honda": ["Shine 100", "Shine SP 125", "CB Shine", "Unicorn 150",
                      "CB Hornet 2.0", "CB350", "CB350RS", "CB500F",
                      "CB300R", "CBR150R", "CBR250R", "Livo"],
            "Bajaj": ["CT 100", "CT 110", "CT 110X", "Platina 100",
                      "Platina H-Gear", "Pulsar 125", "Pulsar 150",
                      "Pulsar 160NS", "Pulsar 180", "Pulsar 200NS",
                      "Pulsar 220F", "Pulsar N160", "Pulsar N250",
                      "Dominar 250", "Dominar 400", "Avenger Street 160",
                      "Avenger Cruise 220"],
            "TVS": ["Radeon", "Star City+", "Metro 100", "Raider 125",
                    "Apache RTR 160", "Apache RTR 160 4V", "Apache RTR 200 4V",
                    "Apache RR 310", "Ronin", "iQube Electric"],
            "Royal Enfield": ["Classic 350", "Bullet 350", "Meteor 350",
                               "Thunderbird", "Himalayan", "Hunter 350",
                               "Super Meteor 650", "Interceptor 650",
                               "Continental GT 650", "Guerrilla 450",
                               "Himalayan 450"],
            "KTM": ["125 Duke", "200 Duke", "250 Duke", "390 Duke",
                    "RC 125", "RC 200", "RC 390", "250 Adventure",
                    "390 Adventure", "390 SMC R"],
            "Yamaha": ["FZ-S FI V4", "FZ-X", "FZS 25", "R15 V4",
                       "R15M", "MT-15 V2", "MT-03", "YZF-R3",
                       "XSR 155", "FZ 25"],
            "Suzuki": ["Gixxer 150", "Gixxer 250", "Gixxer SF 250",
                       "V-Strom SX 250", "Intruder 150"],
            "Kawasaki": ["Ninja 300", "Ninja 400", "Ninja 650", "Ninja ZX-4R",
                         "Z400", "Z650", "Versys 650", "Versys-X 300"],
            "Ola Electric": ["S1 Pro", "S1 X", "S1 Air", "S1 X+"],
            "Ather": ["450X", "450 Apex", "450S"],
            "Revolt": ["RV400", "RV300"],
            "Jawa": ["42", "Perak", "Classic", "42 Bobber"],
            "Yezdi": ["Roadster", "Scrambler", "Adventure"],
            "BMW Motorrad": ["G 310 R", "G 310 GS", "F 850 GS"],
        },
    },

    # ── SCOOTER ──────────────────────────────────────────────────────────────
    "scooter": {
        "label": "Scooter / Moped",
        "brands": {
            "Honda": ["Activa 6G", "Activa 125", "Activa 125 Premium",
                      "Dio", "Grazia 125", "Aviator", "Cliq"],
            "TVS": ["Jupiter", "Jupiter 125", "Ntorq 125", "Ntorq 125 Race XP",
                    "Zest 110", "Scooty Pep+", "Scooty Streak", "XL100",
                    "iQube S", "iQube ST"],
            "Hero": ["Destini 125", "Destini 125 Xtec", "Maestro Edge 110",
                     "Maestro Edge 125", "Pleasure+", "Xoom 110"],
            "Suzuki": ["Access 125", "Burgman Street 125", "Avenis 125",
                       "Swish 125"],
            "Yamaha": ["Fascino 125 FI", "Ray ZR 125 FI", "Ray ZR Street Rally",
                       "Aerox 155"],
            "Bajaj": ["Chetak Electric", "Chetak Premium", "Chetak Urbane"],
            "Ola Electric": ["S1 Pro Gen 2", "S1 Air", "S1 X", "S1 X+"],
            "Ather": ["450X Gen 3", "450 Apex", "450S"],
            "Ampere": ["Magnus EX", "Primus", "Nexus", "Reo Plus"],
            "Okinawa": ["Praise Pro", "iPraise+", "Ridge+", "Dual 100"],
            "Simple Energy": ["Simple One"],
            "Pure EV": ["EPluto 7G", "ETrance NEO"],
        },
    },

    # ── CAR ──────────────────────────────────────────────────────────────────
    "car": {
        "label": "Car / Sedan / Hatchback",
        "brands": {
            "Maruti Suzuki": ["Alto K10", "Alto 800", "S-Presso",
                               "Celerio", "Wagon R", "Swift",
                               "Baleno", "Ignis", "Dzire",
                               "Ciaz", "XL6", "Ertiga"],
            "Hyundai": ["Santro", "Grand i10 Nios", "i20",
                        "i20 N Line", "Verna", "Aura",
                        "Exter", "Ioniq 6"],
            "Tata": ["Tiago", "Tiago EV", "Tigor",
                     "Tigor EV", "Altroz", "Altroz EV"],
            "Honda": ["Jazz", "City 4th Gen", "City 5th Gen",
                      "City e:HEV", "Amaze"],
            "Toyota": ["Glanza", "Camry Hybrid", "Yaris"],
            "Volkswagen": ["Polo", "Virtus GT", "Virtus"],
            "Skoda": ["Slavia", "Fabia", "Rapid"],
            "Renault": ["Kwid", "Kiger", "Triber"],
            "Nissan": ["Magnite", "Kicks"],
            "Kia": ["Carnival"],
            "MG": ["Comet EV"],
            "BYD": ["Seal", "Atto 3"],
            "Citroen": ["C3", "eC3"],
        },
    },

    # ── SUV / MUV ────────────────────────────────────────────────────────────
    "suv": {
        "label": "SUV / MUV / Crossover",
        "brands": {
            "Maruti Suzuki": ["Brezza", "Grand Vitara", "Fronx",
                               "Jimny", "Invicto"],
            "Hyundai": ["Venue", "Venue N Line", "Creta",
                        "Creta N Line", "Alcazar", "Tucson",
                        "Santa Fe", "Ioniq 5"],
            "Tata": ["Nexon", "Nexon EV", "Punch",
                     "Punch EV", "Harrier", "Harrier EV",
                     "Safari", "Safari EV"],
            "Mahindra": ["KUV100", "XUV300", "XUV400 EV",
                         "XUV3XO", "Scorpio N", "Scorpio Classic",
                         "XUV700", "Thar", "Thar Roxx", "Bolero",
                         "Bolero Neo", "BE 6e", "XEV 9e"],
            "Toyota": ["Urban Cruiser Hyryder", "Innova Crysta",
                       "Innova HyCross", "Fortuner",
                       "Fortuner Legender", "Land Cruiser"],
            "Honda": ["Elevate", "WR-V", "BR-V"],
            "Kia": ["Sonet", "Sonet X-Line", "Seltos",
                    "Seltos X-Line", "Carens", "EV6"],
            "MG": ["Hector", "Hector Plus", "Astor",
                   "Gloster", "Windsor EV", "ZS EV"],
            "Jeep": ["Compass", "Meridian", "Wrangler", "Grand Cherokee"],
            "Ford": ["EcoSport", "Endeavour"],
            "Skoda": ["Kushaq", "Kodiaq"],
            "Volkswagen": ["Taigun", "Tiguan"],
            "Renault": ["Duster", "Captur"],
            "Nissan": ["Kicks", "X-Trail"],
            "BMW": ["X1", "X3", "X5", "iX1", "iX"],
            "Mercedes-Benz": ["GLA", "GLC", "GLE", "EQB", "EQS SUV"],
            "Audi": ["Q3", "Q5", "Q7", "e-tron", "Q8 e-tron"],
            "Volvo": ["XC40", "XC60", "XC90", "C40 Recharge"],
            "Lexus": ["UX", "NX", "RX", "LX"],
            "Land Rover": ["Defender", "Discovery", "Range Rover Sport",
                           "Range Rover", "Freelander"],
            "Hyundai Ioniq": ["Ioniq 5", "Ioniq 6"],
            "BYD": ["Atto 3", "Seal U"],
        },
    },

    # ── TRUCK / COMMERCIAL ───────────────────────────────────────────────────
    "truck": {
        "label": "Truck / Tempo / Commercial",
        "brands": {
            "Tata": ["Ace Gold", "Ace HT", "Ace EV",
                     "Intra V30", "Intra V50", "Yodha",
                     "407", "609", "712",
                     "1109", "1512", "Prima",
                     "Ultra 1014", "Signa 4923"],
            "Mahindra": ["Bolero Pickup", "Bolero Camper",
                         "Jeeto", "Jeeto Plus",
                         "Supro Minitruck", "Supro Profit Truck",
                         "Blazo X 25", "Blazo X 35"],
            "Ashok Leyland": ["Dost Plus", "Dost Strong",
                               "Partner", "MiTR",
                               "Ecomet 1415", "Ecomet 1615",
                               "Captain 4225", "Boss"],
            "Eicher": ["Pro 2049", "Pro 3015", "Pro 6016",
                       "Pro 8031", "Eicher 950"],
            "BharatBenz": ["914R", "1015R", "1215R",
                           "3128R", "4028R"],
            "Force Motors": ["Traveller", "Gurkha",
                              "T1N", "Trax Cruiser"],
            "Piaggio": ["Ape City", "Ape HT Xtra",
                        "Ape Truk Plus", "Ape Electrik"],
            "Bajaj": ["Maxima Z", "Maxima C",
                      "RE Compact", "RE 4 Stroke"],
        },
    },

    # ── BUS / MINIBUS ────────────────────────────────────────────────────────
    "bus": {
        "label": "Bus / Minibus",
        "brands": {
            "Tata": ["Starbus Ultra 4/40", "Starbus 9m",
                     "LP 713", "LP 1510", "LPO 1618",
                     "LPT 709", "LPT 909", "Cityride"],
            "Ashok Leyland": ["Lynx", "Oyster", "Eagle",
                               "Viking", "Sunshine", "Janbus",
                               "E-Bus", "Circuit"],
            "Volvo": ["B9R", "B11R", "8400", "9400",
                      "B7R", "BZR (Electric)"],
            "Mercedes-Benz": ["OC 500 RF", "O 500 M",
                               "Tourismo", "Citaro"],
            "SML Isuzu": ["Samrat GS", "S7", "Express",
                          "S7 Luxury"],
            "Eicher": ["Skyline Pro", "Skyline Pro Elite",
                       "Starline 2049"],
            "Force Motors": ["Traveller 13", "Traveller 17",
                              "Traveller 26", "Toofan",
                              "Cruiser 4020"],
            "Mahindra": ["Tourister", "Cosmo", "Xylo"],
            "Marcopolo": ["Paradiso 1600 LD", "Paradiso G7",
                          "Viale BRT"],
            "MSRTC / KSRTC": ["Shivneri", "Asiad", "Volvo AC",
                               "Semi-Luxury", "Ordinary"],
        },
    },
}


def catalog_json_string() -> str:
    return json.dumps(CATALOG)


def validate_selection(vehicle_type: str, vehicle_subtype: str, brand: str, model: str) -> None:
    t = vehicle_type.strip().lower()
    if t not in CATALOG:
        return  # allow custom entries
    block = CATALOG[t]
    if brand and brand not in block.get("brands", {}):
        return  # allow custom brands