"""Portable road-to-ground transition bounded by the two authored heights."""
def height(source, edge, distance, blend):
    t=max(0.,min(1.,distance/max(blend,.1)))
    weight=t*t*t*(t*(t*6-15)+10)
    # Extrapolating the road's lateral slope can excavate the ground when a
    # brush lifts only one side. Blend the actual endpoint heights instead.
    return edge+(source-edge)*weight
