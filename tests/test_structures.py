import unittest
from lexref.structures import Target, StdCoordinate as Sc, \
    InconsistentTargetError, JoiningError

from lexref.model import AxisRole, Value
from lexref.structures import Cycle


doc = Sc('PND', 'TEU', AxisRole.document)


def get_data():
    return [  # context, target, result, document
        (
            Target([Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'V', AxisRole.container)]),
            Target([Sc('TIT', 'I', AxisRole.container),
                    Sc('CHP', 'A', AxisRole.container)]),
            Target([Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'I', AxisRole.container),
                    Sc('CHP', 'A', AxisRole.container)]),
            Target([doc, Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'I', AxisRole.container),
                    Sc('CHP', 'A', AxisRole.container)]),
        ),
        (
            Target([Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'V', AxisRole.container)]),
            Target([Sc('PRT', '2', AxisRole.container)]),
            Target([Sc('PRT', '2', AxisRole.container)]),
            Target([doc, Sc('PRT', '2', AxisRole.container)]),
        ),
        (
            Target([Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'V', AxisRole.container)]),
            Target([Sc('ART', '2', AxisRole.leaf)]),
            Target([Sc('ART', '2', AxisRole.leaf)]),
            Target([doc, Sc('ART', '2', AxisRole.leaf)]),
        ),
        (
            Target([Sc('PRT', '1', AxisRole.container)]),
            Target([Sc('ART', '2', AxisRole.leaf),
                    Sc('PG', '2', AxisRole.paragraph),
                    Sc('LTR', 'b', AxisRole.paragraph)]),
            Target([Sc('ART', '2', AxisRole.leaf),
                    Sc('PG', '2', AxisRole.paragraph),
                    Sc('LTR', 'b', AxisRole.paragraph)]),
            Target([doc, Sc('ART', '2', AxisRole.leaf),
                    Sc('PG', '2', AxisRole.paragraph),
                    Sc('LTR', 'b', AxisRole.paragraph)]),
        ),
    ], ['#toc-PRT_1-TIT_V', '#toc-TIT_I-CHP_A', '#toc-PRT_1-TIT_I-CHP_A',
        '/eu/TEU/TOC/#toc-PRT_1-TIT_I-CHP_A', '#toc-PRT_1-TIT_V', '#toc-PRT_2',
        '#toc-PRT_2', '/eu/TEU/TOC/#toc-PRT_2', '#toc-PRT_1-TIT_V', '#ART_2',
        '#ART_2', '/eu/TEU/ART_2/', '#toc-PRT_1', '#ART_2-2-b', '#ART_2-2-b',
        '/eu/TEU/ART_2/#2-b']


class TestTarget(unittest.TestCase):

    def setUp(self) -> None:
        self.data, self.hrefs = get_data()

    def test_contextualize(self):
        for context, target, result, documented in self.data:
            target.contextualize(container=context)
            self.assertEqual(result, target)
            target.contextualize(container=context)
            self.assertEqual(result, target)
            target.contextualize(document=doc)
            self.assertEqual(documented, target)
            target.contextualize(document=doc)
            self.assertEqual(documented, target)

    def test_role(self):
        self.assertEqual(AxisRole.container, self.data[0][0].role)
        self.assertEqual(AxisRole.container, self.data[0][2].role)
        self.assertEqual(
            AxisRole.mixed,
            Target([Sc('PRT', '1', AxisRole.document),
                    Sc('ART', 'V', AxisRole.leaf)]).role)
        self.assertRaises(
            InconsistentTargetError,
            lambda: Target([Sc('PRT', '1', AxisRole.container),
                            Sc('ART', 'V', AxisRole.leaf)]).role)

    def test_href(self):
        for targets in self.data:
            for target in targets:
                self.assertEqual(self.hrefs.pop(0), target.get_href(''))

    def test_join(self):
        t1 = Target([Sc('PND', 'TFEU', AxisRole.document),
                     Sc('ART', 'V', AxisRole.leaf)])
        t2 = Target([Sc('ART', 'V', AxisRole.leaf)])
        t3 = Target([t2[0]])
        self.assertFalse(t2.has_backref)
        t2.insert(0, Sc('TRT', 'XPREVX', AxisRole.document))
        t2.join(Cycle(4, [t1]))
        t3.insert(0, t1[0])
        self.assertEqual(t3, t2)
        t1 = Target([Sc('CELEX', '32013R0575', AxisRole.document),
                     Sc('PRT', '1', AxisRole.container),
                     Sc('TIT', 'V', AxisRole.container)])
        t2 = Target([Sc('TIT', 'XPREVX', AxisRole.container),
                     Sc('CHP', 'A', AxisRole.container)])
        t2.join(Cycle(4, [t1]))
        self.assertEqual(
            Target([Sc('CELEX', '32013R0575', AxisRole.document),
                    Sc('PRT', '1', AxisRole.container),
                    Sc('TIT', 'V', AxisRole.container),
                    Sc('CHP', 'A', AxisRole.container)]),
            t2
        )
        t1 = Target([Sc('PRG', 'XPREVX', AxisRole.paragraph),
                     Sc('LTR', 'a', AxisRole.paragraph)])
        self.assertRaises(JoiningError, lambda: Target.join(t1, Cycle(4, [t2])))

    def test_create(self):
        data = get_data()
        t1 = data[0][0][-2]
        self.assertEqual(t1, Target.create(t1.get_href('')[1:]))
        self.assertEqual(t1, Target.create(t1))
        self.assertEqual(
            t1,
            Target.create([{'axis': co.axis, 'value': co.value} for co in t1])
        )
        self.assertEqual(Target.create('toc-ANX'),
                         Target([Sc('ANX', None, AxisRole.container)]))


if __name__ == '__main__':
    unittest.main()
