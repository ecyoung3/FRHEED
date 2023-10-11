"""
Material properties for use in computations.
"""

from dataclasses import dataclass
from enum import Enum


# Reference (Table 30.1):
# Adachi, S. (2017). III-V Ternary and Quaternary Compounds.
# Springer Handbook of Electronic and Photonic Materials, 1–1.
# doi:10.1007/978-3-319-48933-9_30


BINARY_LATTICE_PARAMETERS = {  # at 300 K
    "AlN": {
        "Zinc blende": {
            "a": 4.38,  # in Angstroms
        },
        "Wurtzite": {
            "a": 3.112,
            "c": 4.982,
        },
    },
    "AlP": {
        "Zinc blende": {
            "a": 5.4635,
        },
    },
    "AlAs": {
        "Zinc blende": {
            "a": 5.66139,
        },
    },
    "AlSb": {
        "Zinc blende": {
            "a": 6.1355,
        },
    },
    "α-GaN": {  # alpha (α) is Alt+224
        "Wurtzite": {
            "a": 3.1896,
            "c": 5.1855,
        }
    },
    "ß-GaN": {  # beta (ß) is Alt+225
        "Zinc blende": {
            "a": 4.52,
        },
    },
    "GaP": {
        "Zinc blende": {
            "a": 5.4508,
        },
    },
    "GaAs": {
        "Zinc blende": {
            "a": 5.65330,
        },
    },
    "GaSb": {
        "Zinc blende": {
            "a": 6.09593,
        },
    },
    "InN": {
        "Zinc blende": {
            "a": 4.986,
        },
        "Wurtzite": {
            "a": 3.548,
            "c": 5.760,
        },
    },
    "InP": {
        "Zinc blende": {
            "a": 5.8690,
        },
    },
    "InAs": {
        "Zinc blende": {
            "a": 6.0583,
        },
    },
    "InSb": {
        "Zinc blende": {
            "a": 6.47937,
        },
    },
}


def compute_ternary_parameters():
    pass  # TODO


class CrystalStructure(Enum):
    WURTZITE = "Wurtzite"
    ZINC_BLENDE = "Zinc blende"


@dataclass
class Material:
    compound: str
    structure: CrystalStructure


if __name__ == "__main__":
    pass
