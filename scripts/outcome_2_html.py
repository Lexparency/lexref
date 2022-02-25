import os
import json

from lexref import Reflector
from tests.test_e2e import DATA_PATH as TEST_DATA

MISSUNDERSTOODS = os.path.join(os.path.dirname(TEST_DATA), 'missunderstoods.json')


for fp, out in [('MISSUNDERSTOODS', 'missunderstoods'), ('TEST_DATA', 'outcome')]:
    with open(eval(fp), encoding='utf-8') as f:
        data = json.load(f)

    output = ''

    for language, list_ in data.items():
        output += f'<h2>{language}</h2>\n<ol>\n'
        reflector = Reflector(language, 'markup', unclose=True)
        for item in list_:
            li = reflector(item['input'])
            # li = item['markup']
            output += f'<li>{li}</li>\n'
        output += '</ol>\n'

    output += "<hr/>" * 5

    output = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Reflex Check</title>
    </head>
    <body>{output}
    </body>
    </html>"""

    with open(os.path.join(os.path.dirname(__file__), out + '.html'), encoding='utf-8', mode='w') as f:
        f.write(output)


if __name__ == '__main__':
    print('Done')
