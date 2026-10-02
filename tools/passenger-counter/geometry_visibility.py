"""Explain when configured passage regions fall outside the camera image."""


def boundary_visibility(counter, door, width, height):
    x1,y1,x2,y2=door
    if width<=0 or height<=0 or x2<=x1 or y2<=y1:
        raise ValueError('Invalid frame or door dimensions')
    start,end,limit=(x1,x2,width) if counter.axis=='x' else (y1,y2,height)
    low=start+(end-start)*counter.low
    high=start+(end-start)*counter.high
    result={'low_pixel':low,'high_pixel':high,'low_region_visible':low>0,
            'high_region_visible':high<limit}
    if counter.transverse_exit is not None:
        result['transverse_exit_region_visible']=y1+(y2-y1)*counter.transverse_exit<height
    result['has_invisible_axis_region']=not result['low_region_visible'] or not result['high_region_visible']
    # A doorway may still count a lateral approach; this diagnoses a missing
    # visible region and must never silently modify thresholds or invent a count.
    result['lateral_route_possible']=counter.geometry=='doorway'
    return result
