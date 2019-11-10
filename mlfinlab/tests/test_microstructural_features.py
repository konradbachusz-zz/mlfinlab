"""
Test various functions regarding chapter 18: Microstructural Features.
"""

import unittest
import os
import numpy as np
import pandas as pd

from mlfinlab.microstructural_features.encoding import encode_tick_rule_array
from mlfinlab.microstructural_features.entropy import get_plug_in_entropy, get_shannon_entropy, get_lempel_ziv_entropy
from mlfinlab.microstructural_features import (get_vpin, get_bar_based_amihud_lambda, get_bar_based_kyle_lambda,
                                               get_bekker_parkinson_vol, get_corwin_schultz_estimator,
                                               get_bar_based_hasbrouck_lambda, get_roll_impact, get_roll_measure,
                                               quantile_mapping, MicrostructuralFeaturesGenerator)
from mlfinlab.util import get_bvc_buy_volume
from mlfinlab.data_structures import get_volume_bars


class TestMicrostructuralFeatures(unittest.TestCase):
    """
    Test get_inter_bar_features, test_first_generation, test_second_generation, test_misc
    """

    def setUp(self):
        """
        Set the file path for the sample dollar bars data.
        """
        project_path = os.path.dirname(__file__)
        self.path = project_path + '/test_data/dollar_bar_sample.csv'
        self.trades_path = project_path + '/test_data/tick_data.csv'
        self.data = pd.read_csv(self.path, index_col='date_time', parse_dates=[0])
        self.data.index = pd.to_datetime(self.data.index)

    def test_first_generation(self):
        """
        Test first generation intra-bar features
        """

        roll_measure = get_roll_measure(self.data.close, window=20)
        roll_impact = get_roll_impact(self.data.close, self.data.cum_dollar, window=20)
        corwin_schultz = get_corwin_schultz_estimator(self.data.high, self.data.low, window=20)
        bekker_parkinson = get_bekker_parkinson_vol(self.data.high, self.data.low, window=20)

        # Shape assertions
        self.assertEqual(self.data.shape[0], roll_measure.shape[0])
        self.assertEqual(self.data.shape[0], roll_impact.shape[0])
        self.assertEqual(self.data.shape[0], corwin_schultz.shape[0])
        self.assertEqual(self.data.shape[0], bekker_parkinson.shape[0])

        # Roll measure/impact assertions
        self.assertAlmostEqual(roll_measure.max(), 7.1584, delta=1e-4)
        self.assertAlmostEqual(roll_measure.mean(), 2.341, delta=1e-3)
        self.assertAlmostEqual(roll_measure[25], 1.176, delta=1e-3)  # Test some random value

        self.assertAlmostEqual(roll_impact.max(), 1.022e-7, delta=1e-7)
        self.assertAlmostEqual(roll_impact.mean(), 3.3445e-8, delta=1e-7)
        self.assertAlmostEqual(roll_impact[25], 1.6807e-8, delta=1e-4)

        # Test Corwin-Schultz
        self.assertAlmostEqual(corwin_schultz.max(), 0.01652, delta=1e-4)
        self.assertAlmostEqual(corwin_schultz.mean(), 0.00151602, delta=1e-4)
        self.assertAlmostEqual(corwin_schultz[25], 0.00139617, delta=1e-4)

        self.assertAlmostEqual(bekker_parkinson.max(), 0.018773, delta=1e-4)
        self.assertAlmostEqual(bekker_parkinson.mean(), 0.001456, delta=1e-4)
        self.assertAlmostEqual(bekker_parkinson[25], 0.000517, delta=1e-4)

    def test_second_generation_intra_bar(self):
        """
        Test intra-bar second generation features
        """
        kyle_lambda = get_bar_based_kyle_lambda(self.data.close, self.data.cum_vol, window=20)
        amihud_lambda = get_bar_based_amihud_lambda(self.data.close, self.data.cum_dollar, window=20)
        hasbrouck_lambda = get_bar_based_hasbrouck_lambda(self.data.close, self.data.cum_dollar, window=20)

        # Shape assertions
        self.assertEqual(self.data.shape[0], kyle_lambda.shape[0])
        self.assertEqual(self.data.shape[0], amihud_lambda.shape[0])
        self.assertEqual(self.data.shape[0], hasbrouck_lambda.shape[0])

        # Test Kyle Lambda
        self.assertAlmostEqual(kyle_lambda.max(), 0.000163423, delta=1e-6)
        self.assertAlmostEqual(kyle_lambda.mean(), 7.02e-5, delta=1e-6)
        self.assertAlmostEqual(kyle_lambda[25], 7.76e-5, delta=1e-6)  # Test some random value

        # Test Amihud Lambda
        self.assertAlmostEqual(amihud_lambda.max(), 4.057838e-11, delta=1e-13)
        self.assertAlmostEqual(amihud_lambda.mean(), 1.7213e-11, delta=1e-13)
        self.assertAlmostEqual(amihud_lambda[25], 1.8439e-11, delta=1e-13)

        # Test Hasbrouck lambda
        self.assertAlmostEqual(hasbrouck_lambda.max(), 3.39527e-7, delta=1e-10)
        self.assertAlmostEqual(hasbrouck_lambda.mean(), 1.44037e-7, delta=1e-10)
        self.assertAlmostEqual(hasbrouck_lambda[25], 1.5433e-7, delta=1e-10)

    def test_third_generation(self):
        """
        Test third generation features
        """
        bvc_buy_volume = get_bvc_buy_volume(self.data.close, self.data.cum_vol, window=20)
        vpin_1 = get_vpin(self.data.cum_vol, bvc_buy_volume)
        vpin_20 = get_vpin(self.data.cum_vol, bvc_buy_volume, window=20)

        self.assertEqual(self.data.shape[0], vpin_1.shape[0])
        self.assertEqual(self.data.shape[0], vpin_20.shape[0])

        self.assertAlmostEqual(vpin_1.max(), 0.999, delta=1e-3)
        self.assertAlmostEqual(vpin_1.mean(), 0.501, delta=1e-3)
        self.assertAlmostEqual(vpin_1[25], 0.554, delta=1e-3)

        self.assertAlmostEqual(vpin_20.max(), 0.6811, delta=1e-3)
        self.assertAlmostEqual(vpin_20.mean(), 0.500, delta=1e-3)
        self.assertAlmostEqual(vpin_20[45], 0.4638, delta=1e-3)

    def test_tick_rule_encoding(self):
        """
        Test tick rule encoding function
        """
        with self.assertRaises(ValueError):
            encode_tick_rule_array([-1, 1, 0, 20000000])

        encoded_tick_rule = encode_tick_rule_array([-1, 1, 0, 0])
        self.assertEqual('bacc', encoded_tick_rule)

    def test_entropy_calculations(self):
        """
        Test entropy functions
        """
        message = 'abcaa'
        message_array = ['a', 'b', 'c', 'a', 'a']
        shannon = get_shannon_entropy(message)
        plug_in = get_plug_in_entropy(message, word_length=1)
        plug_in_arr = get_plug_in_entropy(message_array, word_length=1)
        lempel = get_lempel_ziv_entropy(message)

        self.assertEqual(plug_in, plug_in_arr)
        self.assertAlmostEqual(shannon, 1.3709, delta=1e-3)
        self.assertAlmostEqual(lempel, 0.8, delta=1e-3)

    def test_csv_format(self):
        """
        Asserts that the csv data being passed is of the correct format.
        """
        wrong_date = ['2019-41-30', 200.00, np.int64(5)]
        wrong_price = ['2019-01-30', 'asd', np.int64(5)]
        wrong_volume = ['2019-01-30', 200.00, '1.5']
        too_many_cols = ['2019-01-30', 200.00, np.int64(5), 'Limit order', 'B23']

        # pylint: disable=protected-access
        self.assertRaises(ValueError,
                          MicrostructuralFeaturesGenerator._assert_csv(pd.DataFrame(wrong_date).T))
        # pylint: disable=protected-access
        self.assertRaises(AssertionError,
                          MicrostructuralFeaturesGenerator._assert_csv,
                          pd.DataFrame(too_many_cols).T)
        # pylint: disable=protected-access
        self.assertRaises(AssertionError,
                          MicrostructuralFeaturesGenerator._assert_csv,
                          pd.DataFrame(wrong_price).T)
        # pylint: disable=protected-access
        self.assertRaises(AssertionError,
                          MicrostructuralFeaturesGenerator._assert_csv,
                          pd.DataFrame(wrong_volume).T)

    def test_feature_generator_function(self):
        """
        Test validity of MicrostructuralFeaturesGenerator
        """
        # Encode volumes and pct changes
        df_trades = pd.read_csv(self.trades_path, parse_dates=[0])
        df_trades['log_ret'] = np.log(df_trades.Price / df_trades.Price.shift(1)).dropna()
        non_null_log_ret = df_trades[df_trades.log_ret != 0].log_ret.dropna()

        # Take unique volumes only
        volume_mapping = quantile_mapping(df_trades.Volume.drop_duplicates(), num_letters=10)

        returns_mapping = quantile_mapping(non_null_log_ret, num_letters=10)

        # Compress bars from ticks
        compressed_bars = get_volume_bars(self.trades_path, threshold=20, verbose=False)
        compressed_bars.set_index('date_time', inplace=True)
        compressed_bars.index = pd.to_datetime(compressed_bars.index)
        bar_index = compressed_bars.index

        # Test None input ValureError raise
        with self.assertRaises(ValueError):
            MicrostructuralFeaturesGenerator(None, bar_index, volume_encoding=volume_mapping,
                                             pct_encoding=returns_mapping)

        gen = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=volume_mapping,
                                               pct_encoding=returns_mapping)
        gen_no_entropy = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=None,
                                                          pct_encoding=None)
        gen_csv = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=volume_mapping,
                                                   pct_encoding=returns_mapping)
        gen_1 = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=volume_mapping,
                                                 pct_encoding=returns_mapping, batch_size=1)
        gen_20 = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=volume_mapping,
                                                  pct_encoding=returns_mapping, batch_size=20)
        gen_df = MicrostructuralFeaturesGenerator(df_trades, bar_index, volume_encoding=volume_mapping,
                                                  pct_encoding=returns_mapping, batch_size=20)
        features = gen.batch_run(to_csv=False, verbose=False)
        features_1 = gen_1.batch_run(to_csv=False, verbose=False)
        features_20 = gen_20.batch_run(to_csv=False, verbose=False)
        features_from_df = gen_df.batch_run(to_csv=False, verbose=False)
        features_no_entropy = gen_no_entropy.batch_run(verbose=False)

        # No volume/pct entropy columns check
        with self.assertRaises(KeyError):
            features['tick_rule_entropy'] += features_no_entropy['volume_entropy_plug_in']

        with self.assertRaises(KeyError):
            features['tick_rule_entropy'] = features_no_entropy['pct_entropy_plug_in']

        gen_csv.batch_run(to_csv=True, output_path='features.csv')
        features_from_csv = pd.read_csv('features.csv', parse_dates=[0])

        self.assertTrue((features.values == features_1.values).all())
        self.assertTrue((features.values == features_20.values).all())
        self.assertTrue((features.values == features_from_df.values).all())

        features.set_index('date_time', inplace=True)
        features_from_csv.set_index('date_time', inplace=True)

        self.assertAlmostEqual((features - features_from_csv).sum().sum(), 0, delta=1e-12)

        self.assertEqual(bar_index.shape[0], features.shape[0])
        self.assertEqual(compressed_bars.loc[features.index].shape[0], compressed_bars.shape[0])

        os.remove('features.csv')

    def test_inter_bar_feature_values(self):
        """
        Test entropy, misc, inter-bar feature generation
        """
        # Encode volumes and pct changes
        df_trades = pd.read_csv(self.trades_path, parse_dates=[0])
        df_trades['log_ret'] = np.log(df_trades.Price / df_trades.Price.shift(1)).dropna()
        unique_volumes = df_trades.Volume.drop_duplicates()
        non_null_log_ret = df_trades[df_trades.log_ret != 0].log_ret.dropna()

        volume_mapping = quantile_mapping(unique_volumes, num_letters=10)
        returns_mapping = quantile_mapping(non_null_log_ret, num_letters=10)

        # Compress bars from ticks
        compressed_bars = get_volume_bars(self.trades_path, threshold=20, verbose=False)
        compressed_bars.set_index('date_time', inplace=True)
        compressed_bars.index = pd.to_datetime(compressed_bars.index)
        bar_index = compressed_bars.index

        gen = MicrostructuralFeaturesGenerator(self.trades_path, bar_index, volume_encoding=volume_mapping,
                                               pct_encoding=returns_mapping)

        features = gen.batch_run(to_csv=False, verbose=False)
        features.set_index('date_time', inplace=True)

        # Check individual feature values
        # Avg tick size
        self.assertAlmostEqual(features.avg_tick_size.max(), 7.5, delta=1e-1)
        self.assertAlmostEqual(features.avg_tick_size.mean(), 3.4259, delta=1e-4)
        self.assertAlmostEqual(features.avg_tick_size[3], 1.416, delta=1e-3)

        # Tick rule sum
        self.assertAlmostEqual(features.tick_rule_sum.max(), 7.0, delta=1e-1)
        self.assertAlmostEqual(features.tick_rule_sum.mean(), -3.8, delta=1e-4)
        self.assertAlmostEqual(features.tick_rule_sum[3], -10, delta=1e-3)

        # VWAP
        self.assertAlmostEqual(features.vwap.max(), 1311.663, delta=1e-1)
        self.assertAlmostEqual(features.vwap.mean(), 1305.139, delta=1e-4)
        self.assertAlmostEqual(features.vwap[3], 1304.514, delta=1e-3)

        # Kyle lambda
        self.assertAlmostEqual(features.kyle_lambda.max(), 63.775, delta=1e-1)
        self.assertAlmostEqual(features.kyle_lambda.mean(), 9.72389, delta=1e-4)
        self.assertAlmostEqual(features.kyle_lambda[3], 0.0106, delta=1e-3)

        # Amihud lambda
        self.assertAlmostEqual(features.amihud_lambda.max(), 2.723e-5, delta=1e-7)
        self.assertAlmostEqual(features.amihud_lambda.mean(), 4.453e-6, delta=1e-8)
        self.assertAlmostEqual(features.amihud_lambda[3], 6.25144e-9, delta=1e-11)

        # Hasbrouck lambda
        self.assertAlmostEqual(features.hasbrouck_lambda.max(), 0.0015506, delta=1e-5)
        self.assertAlmostEqual(features.hasbrouck_lambda.mean(), 8.1187e-5, delta=1e-8)
        self.assertAlmostEqual(features.hasbrouck_lambda[3], 2.99e-11, delta=1e-13)

        # Tick rule entropy shannon
        self.assertAlmostEqual(features.tick_rule_entropy_shannon.max(), 1.52192, delta=1e-4)
        self.assertAlmostEqual(features.tick_rule_entropy_shannon.mean(), 0.5235, delta=1e-4)
        self.assertAlmostEqual(features.tick_rule_entropy_shannon[3], 0.41381, delta=1e-4)

        # Volume entropy plug-in
        self.assertAlmostEqual(features.volume_entropy_plug_in.max(), 1.1609, delta=1e-4)
        self.assertAlmostEqual(features.volume_entropy_plug_in.mean(), 0.639247, delta=1e-5)
        self.assertAlmostEqual(features.volume_entropy_plug_in[3], 0.46096, delta=1e-5)

        # Volume entropy Lempel-Ziv
        self.assertAlmostEqual(features.volume_entropy_lempel_ziv.max(), 1.0, delta=1e-4)
        self.assertAlmostEqual(features.volume_entropy_plug_in.mean(), 0.63924716, delta=1e-5)
        self.assertAlmostEqual(features.volume_entropy_plug_in[3], 0.460964, delta=1e-5)

        # Pct entropy Lempel-Ziv
        self.assertAlmostEqual(features.pct_entropy_lempel_ziv.max(), 0.8, delta=1e-4)
        self.assertAlmostEqual(features.pct_entropy_lempel_ziv.mean(), 0.541649, delta=1e-5)
        self.assertAlmostEqual(features.pct_entropy_lempel_ziv[3], 0.5, delta=1e-5)