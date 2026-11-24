import unittest
from experiments.place_links import osm_place_url


class PlaceLinkTests(unittest.TestCase):
    def test_only_osm_objects_get_links(self):
        self.assertEqual(osm_place_url('relation/48'), 'https://www.openstreetmap.org/relation/48')
        for source in ('n42','node/0','node/42?x=1','node/3/4','https://evil.example',None):
            with self.subTest(source=source):
                self.assertIsNone(osm_place_url(source))


if __name__=='__main__':unittest.main()
