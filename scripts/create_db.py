import os

import pandas as pd

from lexref.model.tables import SessionManager, Base, group, Tag
from lexref import model

try:
    os.remove(SessionManager.DB_PATH)
except FileNotFoundError:
    pass
self = SessionManager()
Base.metadata.create_all(self.engine)
data_path = os.path.join(
    os.path.dirname(os.path.dirname(model.__file__)), 'static')
with self() as s:
    for table in Base.metadata.sorted_tables:
        if table.name == 'tag':
            continue
        df = pd.read_csv(os.path.join(data_path, f'{table.name}.csv'))
        if table.name in group.enums:
            for tag in set(df['tag']):
                s.add(Tag(tag=tag, group=table.name))
        df.to_sql(table.name, s.bind, index=False, if_exists='append')


if __name__ == '__main__':
    print('Done')
