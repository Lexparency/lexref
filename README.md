# LexRef

LEgislative teXt REFerence extraction.

The lexref package provides markup for references to legislative
texts of the European Union. The resulting markups are anchor
elements pointing to the corresponding articles, paragraphs, or
chapters within the lexparency document model.

## Usage

```python
from lexref import Reflector
reflector = Reflector('EN', 'markup')
reflector('Article 2(1)')
'Article <a title="Article 2(1)" href="#ART_2-1">2(1)</a>'
```

Currently, this package supports three languages:
English (EN), German (DE), and Spanish (ES).