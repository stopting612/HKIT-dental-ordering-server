# tooth_validator.py
"""
Tooth Position Validation Module

Implements FDI (Fédération Dentaire Internationale) Two-Digit Notation System
for adult permanent dentition (32 teeth total)
"""

from typing import List, Dict, Tuple, Optional


class ToothValidator:
    """
    Validates tooth positions according to FDI notation system
    
    FDI System:
    - First digit: Quadrant (1-4)
    - Second digit: Tooth position in quadrant (1-8)
    
    Quadrants:
    1 = Upper Right (UR): 18, 17, 16, 15, 14, 13, 12, 11
    2 = Upper Left (UL):  21, 22, 23, 24, 25, 26, 27, 28
    3 = Lower Left (LL):  31, 32, 33, 34, 35, 36, 37, 38
    4 = Lower Right (LR): 41, 42, 43, 44, 45, 46, 47, 48
    """
    
    # Valid tooth ranges per quadrant
    QUADRANT_RANGES = {
        1: (11, 18),  # Upper Right: 11-18
        2: (21, 28),  # Upper Left: 21-28
        3: (31, 38),  # Lower Left: 31-38
        4: (41, 48),  # Lower Right: 41-48
    }
    
    # All valid tooth numbers (set for O(1) lookup)
    VALID_TEETH = set(range(11, 19)) | set(range(21, 29)) | \
                  set(range(31, 39)) | set(range(41, 49))
    
    # Quadrant names (for user feedback)
    QUADRANT_NAMES = {
        1: "Upper Right (右上)",
        2: "Upper Left (左上)",
        3: "Lower Left (左下)",
        4: "Lower Right (右下)"
    }
    
    # Tooth type names (for user feedback)
    TOOTH_TYPES = {
        1: "Central Incisor (中門牙)",
        2: "Lateral Incisor (側門牙)",
        3: "Canine (犬齒)",
        4: "First Premolar (第一小臼齒)",
        5: "Second Premolar (第二小臼齒)",
        6: "First Molar (第一大臼齒)",
        7: "Second Molar (第二大臼齒)",
        8: "Third Molar/Wisdom (第三大臼齒/智慧齒)"
    }
    
    @classmethod
    def validate_single_tooth(cls, tooth_number: int) -> Dict:
        """
        Validate a single tooth number
        
        Args:
            tooth_number: Integer tooth number (e.g., 11, 26, 48)
        
        Returns:
            {
                "valid": bool,
                "tooth_number": int,
                "quadrant": int (1-4) or None,
                "quadrant_name": str or None,
                "position": int (1-8) or None,
                "tooth_type": str or None,
                "error": str or None
            }
        """
        # Check if tooth number is in valid range
        if tooth_number not in cls.VALID_TEETH:
            # Determine the type of error
            if tooth_number < 11:
                error = f"Invalid tooth number {tooth_number}. Tooth numbers must be between 11-18, 21-28, 31-38, or 41-48."
            elif tooth_number > 48:
                error = f"Invalid tooth number {tooth_number}. Maximum tooth number is 48."
            else:
                # Check which rule was violated
                quadrant = tooth_number // 10
                position = tooth_number % 10
                
                if quadrant not in [1, 2, 3, 4]:
                    error = f"Invalid quadrant {quadrant}. Valid quadrants are 1 (UR), 2 (UL), 3 (LL), 4 (LR)."
                elif position < 1 or position > 8:
                    error = f"Invalid position {position} in quadrant {quadrant}. Valid positions are 1-8."
                else:
                    error = f"Invalid tooth number {tooth_number}."
            
            return {
                "valid": False,
                "tooth_number": tooth_number,
                "quadrant": None,
                "quadrant_name": None,
                "position": None,
                "tooth_type": None,
                "error": error
            }
        
        # Extract quadrant and position
        quadrant = tooth_number // 10
        position = tooth_number % 10
        
        return {
            "valid": True,
            "tooth_number": tooth_number,
            "quadrant": quadrant,
            "quadrant_name": cls.QUADRANT_NAMES[quadrant],
            "position": position,
            "tooth_type": cls.TOOTH_TYPES[position],
            "error": None
        }
    
    @classmethod
    def validate_multiple_teeth(cls, tooth_positions: str) -> Dict:
        """
        Validate multiple tooth positions (comma or space separated)
        
        Args:
            tooth_positions: String of tooth numbers, e.g., "11,12,13" or "11 12 13"
        
        Returns:
            {
                "valid": bool,
                "teeth": List[int],
                "valid_teeth": List[int],
                "invalid_teeth": List[Dict],
                "count": int,
                "error": str or None,
                "quadrants_involved": List[int],
                "is_continuous": bool (for bridge validation)
            }
        """
        # Parse input
        import re
        tooth_numbers_str = re.split(r'[,\s]+', tooth_positions.strip())
        
        # Convert to integers
        try:
            tooth_numbers = [int(t) for t in tooth_numbers_str if t]
        except ValueError as e:
            return {
                "valid": False,
                "teeth": [],
                "valid_teeth": [],
                "invalid_teeth": [],
                "count": 0,
                "error": f"Invalid input format. Please use numbers separated by commas or spaces. Error: {str(e)}",
                "quadrants_involved": [],
                "is_continuous": False
            }
        
        if not tooth_numbers:
            return {
                "valid": False,
                "teeth": [],
                "valid_teeth": [],
                "invalid_teeth": [],
                "count": 0,
                "error": "No tooth positions provided.",
                "quadrants_involved": [],
                "is_continuous": False
            }
        
        # Validate each tooth
        valid_teeth = []
        invalid_teeth = []
        
        for tooth in tooth_numbers:
            result = cls.validate_single_tooth(tooth)
            if result["valid"]:
                valid_teeth.append(tooth)
            else:
                invalid_teeth.append({
                    "tooth_number": tooth,
                    "error": result["error"]
                })
        
        # Determine if all teeth are valid
        all_valid = len(invalid_teeth) == 0
        
        # Analyze valid teeth
        quadrants_involved = list(set([t // 10 for t in valid_teeth]))
        quadrants_involved.sort()
        
        # Check if teeth are continuous (for bridge validation)
        is_continuous = cls._check_continuity(valid_teeth)
        
        # Build response
        response = {
            "valid": all_valid,
            "teeth": tooth_numbers,
            "valid_teeth": valid_teeth,
            "invalid_teeth": invalid_teeth,
            "count": len(tooth_numbers),
            "quadrants_involved": quadrants_involved,
            "is_continuous": is_continuous
        }
        
        # Add error message if there are invalid teeth
        if not all_valid:
            error_details = "; ".join([
                f"Tooth {item['tooth_number']}: {item['error']}"
                for item in invalid_teeth
            ])
            response["error"] = f"Found {len(invalid_teeth)} invalid tooth position(s). {error_details}"
        else:
            response["error"] = None
        
        return response
    
    @classmethod
    def _check_continuity(cls, teeth: List[int]) -> bool:
        """
        Check if teeth are continuous (adjacent)
        
        For bridge validation: teeth must be in sequence
        Example: [11, 12, 13] ✓ continuous
                 [11, 13, 14] ✗ not continuous (missing 12)
        
        Args:
            teeth: List of tooth numbers (must be valid)
        
        Returns:
            True if teeth form a continuous sequence
        """
        if len(teeth) <= 1:
            return True
        
        # Sort teeth
        sorted_teeth = sorted(teeth)
        
        # Check if all in same quadrant
        quadrants = [t // 10 for t in sorted_teeth]
        if len(set(quadrants)) > 1:
            # Teeth span multiple quadrants - check special cases
            # Valid cross-quadrant bridges: 11-21 (upper midline)
            if set(sorted_teeth) == {11, 21}:
                return True
            # Otherwise not continuous
            return False
        
        # Check if sequence is continuous
        for i in range(len(sorted_teeth) - 1):
            if sorted_teeth[i + 1] - sorted_teeth[i] != 1:
                return False
        
        return True
    
    @classmethod
    def get_adjacent_teeth(cls, tooth_number: int) -> Dict:
        """
        Get adjacent teeth (mesial and distal)
        
        Args:
            tooth_number: Valid tooth number
        
        Returns:
            {
                "tooth": int,
                "mesial": int or None (towards midline),
                "distal": int or None (away from midline),
                "adjacent": List[int]
            }
        """
        result = cls.validate_single_tooth(tooth_number)
        if not result["valid"]:
            return {
                "tooth": tooth_number,
                "mesial": None,
                "distal": None,
                "adjacent": [],
                "error": result["error"]
            }
        
        quadrant = tooth_number // 10
        position = tooth_number % 10
        
        # Determine mesial and distal based on quadrant
        if quadrant in [1, 4]:  # Right side (UR, LR)
            # Mesial = towards midline = lower number
            # Distal = away from midline = higher number
            mesial = tooth_number - 1 if position > 1 else None
            distal = tooth_number + 1 if position < 8 else None
        else:  # Left side (UL, LL)
            # Mesial = towards midline = higher number
            # Distal = away from midline = lower number
            mesial = tooth_number + 1 if position < 8 else None
            distal = tooth_number - 1 if position > 1 else None
        
        # Special case: midline crossing (11 ↔ 21, 41 ↔ 31)
        if tooth_number == 11:
            mesial = 21  # Can bridge to 21
        elif tooth_number == 21:
            mesial = 11
        elif tooth_number == 41:
            mesial = 31
        elif tooth_number == 31:
            mesial = 41
        
        adjacent = [t for t in [mesial, distal] if t is not None]
        
        return {
            "tooth": tooth_number,
            "mesial": mesial,
            "distal": distal,
            "adjacent": adjacent,
            "error": None
        }


# Convenience functions for tool integration

def validate_tooth_position(tooth_positions: str) -> Dict:
    """
    Tool function: Validate tooth positions
    
    This function is exposed as a tool for the AI agent
    
    Args:
        tooth_positions: Comma or space-separated tooth numbers
    
    Returns:
        Validation result dictionary
    """
    return ToothValidator.validate_multiple_teeth(tooth_positions)


def get_valid_tooth_ranges() -> Dict:
    """
    Tool function: Get valid tooth number ranges
    
    Returns information about valid tooth numbering system
    """
    return {
        "system": "FDI Two-Digit Notation",
        "total_teeth": 32,
        "quadrants": {
            "1": {
                "name": "Upper Right (右上)",
                "range": "11-18",
                "teeth": list(range(11, 19))
            },
            "2": {
                "name": "Upper Left (左上)",
                "range": "21-28",
                "teeth": list(range(21, 29))
            },
            "3": {
                "name": "Lower Left (左下)",
                "range": "31-38",
                "teeth": list(range(31, 39))
            },
            "4": {
                "name": "Lower Right (右下)",
                "range": "41-48",
                "teeth": list(range(41, 49))
            }
        },
        "examples": {
            "single_crown": "11 (upper right central incisor)",
            "bridge": "14,15,16 (upper right premolars and first molar)",
            "multiple_crowns": "11,21 (upper central incisors)"
        }
    }


# Testing
if __name__ == "__main__":
    print("="*60)
    print("Tooth Position Validator - Test Suite")
    print("="*60)
    
    # Test cases
    test_cases = [
        ("11", "Valid single tooth - UR central incisor"),
        ("48", "Valid single tooth - LR wisdom tooth"),
        ("11,12,13", "Valid continuous bridge - UR"),
        ("14 15 16", "Valid continuous bridge - UR (space separated)"),
        ("11,21", "Valid midline bridge"),
        ("11,13", "Invalid - non-continuous"),
        ("19", "Invalid - out of range"),
        ("50", "Invalid - quadrant doesn't exist"),
        ("abc", "Invalid - not a number"),
        ("11,12,99", "Mixed valid and invalid"),
        ("", "Empty input"),
    ]
    
    for teeth_input, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Input: '{teeth_input}'")
        result = validate_tooth_position(teeth_input)
        print(f"Valid: {result['valid']}")
        if result['valid']:
            print(f"  ✓ Teeth: {result['valid_teeth']}")
            print(f"  ✓ Quadrants: {result['quadrants_involved']}")
            print(f"  ✓ Continuous: {result['is_continuous']}")
        else:
            print(f"  ✗ Error: {result['error']}")
    
    print("\n" + "="*60)
    print("Valid Tooth Ranges Reference:")
    print("="*60)
    ranges = get_valid_tooth_ranges()
    for quad_num, quad_info in ranges['quadrants'].items():
        print(f"Quadrant {quad_num}: {quad_info['name']} → {quad_info['range']}")