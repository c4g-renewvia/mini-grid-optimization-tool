import numpy as np

one_meter_deg = 1 / 111111  # rough conversion from meters to degrees

# 5 x 5 grid
grid_size = 5
grid_lat = np.linspace(-one_meter_deg * grid_size, one_meter_deg * grid_size, grid_size)

grid_lng = np.linspace(-one_meter_deg * grid_size, one_meter_deg * grid_size, grid_size)

# grid of tuples
grid_points = [(lat, lng) for lat in grid_lat for lng in grid_lng]

print(grid_points)
