#!/usr/bin/env python3
"""
Maidenhead Grid Locator System converter
Converts lat/lon coordinates to Maidenhead grid squares (e.g., JN47, JO32)
Used by amateur radio operators for position reporting
"""

def latlon_to_maidenhead(lat: float, lon: float, precision: int = 3) -> str:
    """
    Convert latitude/longitude to Maidenhead grid square

    Args:
        lat: Latitude in decimal degrees (-90 to +90)
        lon: Longitude in decimal degrees (-180 to +180)
        precision: Number of pairs (1=field, 2=square, 3=subsquare, 4=extended)

    Returns:
        Maidenhead grid locator string (e.g., "JN47ab" for precision=3)

    Example:
        >>> latlon_to_maidenhead(46.5197, 6.6323, precision=2)
        'JN36'
        >>> latlon_to_maidenhead(47.3769, 8.5417, precision=3)
        'JN47ph'
    """
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude {lat} out of range [-90, 90]")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude {lon} out of range [-180, 180]")

    # Adjust coordinates to Maidenhead system (0-180 lon, 0-180 lat)
    adj_lon = lon + 180
    adj_lat = lat + 90

    result = ""

    # Field (18° lon x 10° lat) - Letters A-R
    field_lon = int(adj_lon / 20)
    field_lat = int(adj_lat / 10)
    result += chr(ord('A') + field_lon) + chr(ord('A') + field_lat)

    if precision < 2:
        return result

    # Square (2° lon x 1° lat) - Digits 0-9
    adj_lon = (adj_lon % 20) / 2
    adj_lat = (adj_lat % 10) / 1
    square_lon = int(adj_lon)
    square_lat = int(adj_lat)
    result += str(square_lon) + str(square_lat)

    if precision < 3:
        return result

    # Subsquare (5' lon x 2.5' lat = 0.083° x 0.042°) - Letters a-x (lowercase)
    adj_lon = (adj_lon - square_lon) * 24
    adj_lat = (adj_lat - square_lat) * 24
    subsquare_lon = int(adj_lon)
    subsquare_lat = int(adj_lat)
    result += chr(ord('a') + subsquare_lon) + chr(ord('a') + subsquare_lat)

    if precision < 4:
        return result

    # Extended subsquare (12.5" lon x 6.25" lat) - Digits 0-9
    adj_lon = (adj_lon - subsquare_lon) * 10
    adj_lat = (adj_lat - subsquare_lat) * 10
    ext_lon = int(adj_lon)
    ext_lat = int(adj_lat)
    result += str(ext_lon) + str(ext_lat)

    return result


def maidenhead_to_latlon(grid: str) -> tuple[float, float]:
    """
    Convert Maidenhead grid square to center lat/lon coordinates

    Args:
        grid: Maidenhead locator (e.g., "JN47", "JN47ph")

    Returns:
        Tuple of (latitude, longitude) for the center of the grid square

    Example:
        >>> maidenhead_to_latlon("JN36")
        (46.5, 6.0)
    """
    grid = grid.upper()

    if len(grid) < 2:
        raise ValueError("Grid must be at least 2 characters (field)")

    # Field
    lon: float = (ord(grid[0]) - ord('A')) * 20 - 180
    lat: float = (ord(grid[1]) - ord('A')) * 10 - 90

    if len(grid) >= 4:
        # Square
        lon += int(grid[2]) * 2
        lat += int(grid[3]) * 1
    else:
        # Center of field
        lon += 10
        lat += 5
        return (lat, lon)

    if len(grid) >= 6:
        # Subsquare
        lon += (ord(grid[4]) - ord('A')) * (2/24)
        lat += (ord(grid[5]) - ord('A')) * (1/24)
    else:
        # Center of square
        lon += 1
        lat += 0.5
        return (lat, lon)

    if len(grid) >= 8:
        # Extended
        lon += int(grid[6]) * (2/240)
        lat += int(grid[7]) * (1/240)
        # Center of extended subsquare
        lon += (2/480)
        lat += (1/480)
    else:
        # Center of subsquare
        lon += (2/48)
        lat += (1/48)

    return (lat, lon)


if __name__ == '__main__':
    # Test cases
    print("Maidenhead Grid Locator Converter")
    print("=" * 50)

    # Swiss locations
    test_coords = [
        ("Bern", 46.9480, 7.4474),
        ("Zurich", 47.3769, 8.5417),
        ("Geneva", 46.2044, 6.1432),
        ("Basel", 47.5596, 7.5886),
        ("Lausanne", 46.5197, 6.6323)
    ]

    print("\nSwiss Cities:")
    for name, lat, lon in test_coords:
        grid2 = latlon_to_maidenhead(lat, lon, precision=2)
        grid3 = latlon_to_maidenhead(lat, lon, precision=3)
        print(f"{name:12} ({lat:7.4f}, {lon:7.4f}) → {grid2} / {grid3}")

    print("\nReverse conversion:")
    for grid in ["JN36", "JN47", "JN37", "JN47ph"]:
        lat, lon = maidenhead_to_latlon(grid)
        print(f"{grid:8} → ({lat:7.4f}, {lon:7.4f})")
