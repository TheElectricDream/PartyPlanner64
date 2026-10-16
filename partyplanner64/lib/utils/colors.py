"""Distinct colors (port of utils/colors.ts)."""

_kelly_colors = [
    [166, 189, 215],  # very_light_blue
    [128, 62, 117],  # strong_purple
    [255, 179, 0],  # vivid_yellow
    [0, 83, 138],  # strong_blue
    [255, 104, 0],  # vivid_orange
    [129, 112, 102],  # medium_gray
    [193, 0, 32],  # vivid_red
    [206, 162, 98],  # grayish_yellow
    [0, 125, 52],  # vivid_green
    [246, 118, 142],  # strong_purplish_pink
    [255, 122, 92],  # strong_yellowish_pink
    [83, 55, 122],  # strong_violet
    [255, 142, 0],  # vivid_orange_yellow
    [179, 40, 81],  # strong_purplish_red
    [244, 200, 0],  # vivid_greenish_yellow
    [127, 24, 13],  # strong_reddish_brown
    [147, 170, 0],  # vivid_yellowish_green
    [89, 51, 21],  # deep_yellowish_brown
    [241, 58, 19],  # vivid_reddish_orange
    [35, 44, 22],  # dark_olive_green
]


def get_distinct_color(index):
    """Returns a somewhat distinct color based on index key."""
    return _kelly_colors[index % len(_kelly_colors)]


class _ColorQueue:
    """Gives out distinct colors when asked (IColorQueue)."""

    def __init__(self):
        self._index = 0

    def next(self):
        color = get_distinct_color(self._index)
        self._index += 1
        return color


def make_color_queue():
    """Returns a thing that will give out distinct colors when asked."""
    return _ColorQueue()
