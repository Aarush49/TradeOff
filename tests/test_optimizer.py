import unittest
from optimizer import Request, Offer, demo, solve

class OptimizerTests(unittest.TestCase):
    def test_demo(self):
        result = solve(*demo())
        self.assertEqual(result['objective'],7600)
        self.assertEqual([d['allocated'] for d in result['decisions']],[600,500])

    def test_late_alternative(self):
        requests, offers = demo()
        offers[1] = Offer('Supplier T',300,5,12)
        result = solve(requests, offers)
        self.assertEqual([d['allocated'] for d in result['decisions']],[600,200])
        self.assertEqual(result['objective'],11500)

    def test_infeasible(self):
        with self.assertRaisesRegex(ValueError,'No feasible'):
            solve([Request('A',600,1,100,400)],[Offer('S',300,1,5)])

    def test_exhaustive_small_network(self):
        # Independent brute-force oracle checks cost, hard minimums, and routes.
        import itertools
        for capacity in range(4):
            for minimum in range(3):
                requests=[Request('A',2,1,9,minimum),Request('B',2,2,5)]
                offers=[Offer('S',capacity,1,3),Offer('T',2,2,4)]
                costs=[]
                for a,b,t in itertools.product(range(3),repeat=3):
                    if a+b<=capacity and a>=minimum and b+t<=2 and t<=2:
                        costs.append(3*(a+b)+4*t+9*(2-a)+5*(2-b-t))
                if costs:
                    self.assertEqual(solve(requests,offers)['objective'],min(costs))
                else:
                    with self.assertRaises(ValueError):
                        solve(requests,offers)

    def test_minimum_overrides_cost(self):
        result=solve([Request('A',2,1,0,1)],[Offer('S',2,1,10)])
        self.assertEqual(result['decisions'][0]['allocated'],1)

if __name__=='__main__':
    unittest.main()
