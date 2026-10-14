"""Portable lane validation foundation; no Blender or traffic-simulator dependency.

This validates explicit design permissions, not blanket legal compliance. Local
traffic-control exceptions must be supplied by the jurisdiction adapter.
"""
from dataclasses import dataclass, field
from math import isfinite
MAX_LANES = 7

@dataclass(frozen=True)
class TrafficLayout:
    traffic_side: str = 'RIGHT'
    steering_side: str | None = None
    jurisdiction: str = 'US_FL'

    def __post_init__(self):
        if self.traffic_side not in ('RIGHT','LEFT') or self.steering_side not in (None,'RIGHT','LEFT'):
            raise ValueError('Traffic and steering sides must be RIGHT or LEFT')
        if self.jurisdiction == 'US_FL' and self.traffic_side != 'RIGHT':
            raise ValueError('Florida profile requires right-side traffic')

    def incoming_offset(self, from_center):
        """Signed offset in travel-right coordinates; independent of steering side."""
        return from_center if self.traffic_side == 'RIGHT' else -from_center

@dataclass(frozen=True)
class Lane:
    id: str
    width: float = 3.5
    movements: frozenset = field(default_factory=lambda: frozenset({'THROUGH'}))

@dataclass(frozen=True)
class Connector:
    source_lane: str
    destination_lane: str
    movement: str


def validate_lanes(lanes, available, marked_left=1, marked_right=1):
    """Lanes ordered driver's left -> right; turn blocks explicitly designated.

    Multiple turn lanes require their signed/marked lane block to be supplied.
    Curvature, swept envelopes, sight distance and signal conflicts are separate
    later validators; this function does not claim to check them.
    """
    errors=[];n=len(lanes)
    if not 1 <= n <= MAX_LANES:errors.append('Incoming lane count must be 1–7')
    if len({l.id for l in lanes}) != n:errors.append('Lane IDs must be unique')
    if not (0 <= marked_left <= n and 0 <= marked_right <= n):
        errors.append('Turn block count exceeds available lanes');return errors
    if n>1 and marked_left+marked_right>n:
        errors.append('Left and right turn blocks overlap')
    for i,lane in enumerate(lanes):
        if not isfinite(lane.width) or lane.width<=0:errors.append(f'{lane.id}: invalid width')
        if not lane.movements:errors.append(f'{lane.id}: no permitted destination')
        for movement in lane.movements:
            if movement not in available:errors.append(f'{lane.id}: {movement} has no available approach')
            if movement=='LEFT' and i>=marked_left:errors.append(f'{lane.id}: left turn outside designated left block')
            if movement=='RIGHT' and i<n-marked_right:errors.append(f'{lane.id}: right turn outside designated right block')
    return errors


def map_turn_block(source_ids, destination_ids, movement):
    """Order-preserving one-to-one multi-turn mapping. Never collapse into one lane."""
    if movement not in ('LEFT','RIGHT','THROUGH'):raise ValueError('Unsupported movement')
    if not source_ids or len(source_ids)>len(destination_ids):
        raise ValueError('Not enough receiving lanes; add lanes or reduce turn block')
    if len(set(source_ids))!=len(source_ids) or len(set(destination_ids))!=len(destination_ids):
        raise ValueError('Lane IDs must be unique within each block')
    targets=destination_ids[:len(source_ids)] if movement!='RIGHT' else destination_ids[-len(source_ids):]
    return [Connector(s,d,movement) for s,d in zip(source_ids,targets)]


def road_width(incoming, outgoing, median=0.0, shoulders=(0.5,0.5), preferred=0.0):
    """Return (effective, minimum) widths; preferred width cannot squeeze lanes.

    Incoming/outgoing lane widths are independent. Extra width is available for
    shoulders/edge allowance; it never silently changes lane width.
    """
    if not (0 <= len(incoming) <= MAX_LANES and 0 <= len(outgoing) <= MAX_LANES):
        raise ValueError('Each direction supports at most seven lanes')
    widths=[l.width for l in [*incoming,*outgoing]]
    if any(not isfinite(w) or w<=0 for w in widths):raise ValueError('Invalid lane width')
    if len(shoulders)!=2 or any(not isfinite(w) or w<0 for w in [median,*shoulders,preferred]):
        raise ValueError('Invalid median, shoulder or preferred width')
    minimum=sum(widths)+median+sum(shoulders)
    return max(preferred,minimum),minimum


def layout_for_map(scene):
    """Global scene adapter; vehicle steering position is not a road parameter."""
    from .map_settings import traffic_side
    side=traffic_side(scene)
    return TrafficLayout(side,None,
                         'US_FL' if side=='RIGHT' else 'GENERIC_LHT')


def available_movements(a,b,neighbors):
    """Geometric movement choices, not legal U-turn authorization.

    Pick at most one clear continuation. Symmetric forks expose left/right
    instead of incorrectly treating both branches as through destinations.
    """
    from math import atan2,degrees
    dx,dy=b[0]-a[0],b[1]-a[1];angles=[]
    for c in neighbors:
        if tuple(c)==tuple(a):continue
        ex,ey=c[0]-b[0],c[1]-b[1]
        angles.append(degrees(atan2(dx*ey-dy*ex,dx*ex+dy*ey)))
    choices={'UTURN'}
    ordered=sorted(range(len(angles)),key=lambda i:abs(angles[i]))
    through=None
    if ordered and abs(angles[ordered[0]])<=30:
        if len(ordered)==1 or abs(abs(angles[ordered[0]])-abs(angles[ordered[1]]))>1:
            through=ordered[0]
    for i,angle in enumerate(angles):choices.add('THROUGH' if i==through else 'LEFT' if angle>0 else 'RIGHT')
    return choices
