from typing import Deque


YamlValueBase = str | bool | int | float | None
YamlObjectBase = dict[str, YamlValueBase]
YamlListBase = dict[YamlValueBase]
YamlObject = dict[str, YamlValueBase | YamlListBase | YamlObjectBase]
YamlList = list[YamlValueBase | YamlObjectBase | YamlObject]

Data = YamlList | YamlObject | YamlValueBase

Items = Deque[
    YamlObject | YamlList | tuple[
        str,
        Data
    ]
]
