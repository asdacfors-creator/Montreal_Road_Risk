import geopandas as gpd
from shapely.geometry import Point
from montreal_road_risk.spatial.crs import reproject_gdf


def test_reproject_gdf():
    # Setup simple geographic points in Montreal region (WGS84, EPSG:4326)
    geom = [Point(-73.5519, 45.5017)]  # Downtown Montreal
    gdf = gpd.GeoDataFrame(geometry=geom, crs="EPSG:4326")

    # Reproject to approved working CRS (EPSG:32188)
    dest_gdf = reproject_gdf(gdf, "EPSG:32188")

    assert dest_gdf.crs.to_string() == "EPSG:32188"
    assert len(dest_gdf) == 1

    # Centroid coordinate should be projected (approx. x=300000, y=5040000)
    pt = dest_gdf.geometry.iloc[0]
    assert 290000 < pt.x < 310000
    assert 5030000 < pt.y < 5050000
