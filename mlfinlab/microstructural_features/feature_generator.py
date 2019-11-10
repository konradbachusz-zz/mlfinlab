"""
Inter-bar feature generator which uses trades data and bars index to calculate inter-bar features
"""

import pandas as pd
import numpy as np
from mlfinlab.microstructural_features.entropy import get_shannon_entropy, get_plug_in_entropy, get_lempel_ziv_entropy
from mlfinlab.microstructural_features.encoding import encode_array
from mlfinlab.microstructural_features.second_generation import get_trades_based_kyle_lambda, \
    get_trades_based_amihud_lambda, get_trades_based_hasbrouck_lambda
from mlfinlab.microstructural_features.misc import get_avg_tick_size, vwap
from mlfinlab.microstructural_features.encoding import encode_tick_rule_array


# pylint: disable=too-many-instance-attributes

def _crop_data_frame_in_batches(df: pd.DataFrame, chunksize: int):
    # pylint: disable=invalid-name
    """
    Splits df into chunks of chunksize
    :param df: (pd.DataFrame) to split
    :param chunksize: (Int) number of rows in chunk
    :return: (list) of chunks (pd.DataFrames)
    """
    generator_object = []
    for _, chunk in df.groupby(np.arange(len(df)) // chunksize):
        generator_object.append(chunk)
    return generator_object


class MicrostructuralFeaturesGenerator:
    """
    Class which is used to generate inter-bar features when bars are already compressed
    """

    def __init__(self, trades_input: (str, pd.DataFrame), bar_index: pd.DatetimeIndex, batch_size: int = 2e7,
                 volume_encoding: dict = None, pct_encoding: dict = None):
        """
        Constructor
        :param trades_input: (String) Path to the csv file or Pandas Dat Frame containing raw tick data in the format[date_time, price, volume]
        :param bar_index: (pd.DatetimeIndex) bars index used for feature calculations, should be sorted
        :param batch_size: (int) Number of rows to read in from the csv, per batch.
        :param volume_encoding: (dict) Dictionary of encoding trades size anc calculate entropy on encoded messages
        :param pct_encoding: (dict) Dictionary of encoding log returns anc calculate entropy on encoded messages
        """

        if isinstance(trades_input, str):
            self.generator_object = pd.read_csv(trades_input, chunksize=batch_size, parse_dates=[0])
            # Read in the first row & assert format
            first_row = pd.read_csv(trades_input, nrows=1)
            self._assert_csv(first_row)
        elif isinstance(trades_input, pd.DataFrame):
            self.generator_object = _crop_data_frame_in_batches(trades_input, batch_size)
        else:
            raise ValueError('trades_input is neither string(path to a csv file) nor pd.DataFrame')

        # Base properties
        self.bar_index_iterator = iter(bar_index)
        self.current_date_time = self.bar_index_iterator.__next__()

        # Cache properties
        self.price_diff = []
        self.trade_size = []
        self.tick_rule = []
        self.dollar_size = []
        self.log_ret = []

        # Entropy properties
        self.volume_encoding = volume_encoding
        self.pct_encoding = pct_encoding

        # Batch_run properties
        self.prev_price = None
        self.prev_tick_rule = 0

    def batch_run(self, verbose=True, to_csv=False, output_path=None):
        """
        Reads a csv file in batches and then constructs the financial data structure in the form of a DataFrame.
        The csv file must have only 3 columns: date_time, price, & volume.
        :param verbose: (Boolean) Flag whether to print message on each processed batch or not
        :param to_csv: (Boolean) Flag for writing the results of bars generation to local csv file, or to in-memory DataFrame
        :param output_path: (Boolean) Path to results file, if to_csv = True
        :return: (DataFrame or None) Financial data structure
        """

        if to_csv is True:
            header = True  # if to_csv is True, header should be written on the first batch only
            open(output_path, 'w').close()  # Clean output csv file

        # Read csv in batches
        count = 0
        final_bars = []
        cols = ['date_time', 'avg_tick_size', 'tick_rule_sum', 'vwap', 'kyle_lambda', 'amihud_lambda',
                'hasbrouck_lambda']

        # Entropy features columns
        for en_type in ['shannon', 'plug_in', 'lempel_ziv']:
            cols += ['tick_rule_entropy_' + en_type]

        if self.volume_encoding is not None:
            for en_type in ['shannon', 'plug_in', 'lempel_ziv']:
                cols += ['volume_entropy_' + en_type]

        if self.pct_encoding is not None:
            for en_type in ['shannon', 'plug_in', 'lempel_ziv']:
                cols += ['pct_entropy_' + en_type]

        for batch in self.generator_object:
            if verbose:  # pragma: no cover
                print('Batch number:', count)

            list_bars, stop_flag = self._extract_bars(data=batch)

            if to_csv is True:
                pd.DataFrame(list_bars, columns=cols).to_csv(output_path, header=header, index=False, mode='a')
                header = False
            else:
                # Append to bars list
                final_bars += list_bars
            count += 1

            # End of bar index, no need to calculate further
            if stop_flag is True:
                break

        # Return a DataFrame
        if final_bars:
            bars_df = pd.DataFrame(final_bars, columns=cols)
            return bars_df

        # Processed DataFrame is stored in .csv file, return None
        return None

    def _reset_cache(self):
        """
        Reset price_diff, trade_size, tick_rule, log_ret arrays to empty when bar is formed and features are
        calculated
        :return:
        """
        self.price_diff = []
        self.trade_size = []
        self.tick_rule = []
        self.dollar_size = []
        self.log_ret = []

    def _extract_bars(self, data):
        """
        For loop which calculates features for formed bars using trades data
        :param data: Contains 3 columns - date_time, price, and volume.
        """

        # Iterate over rows
        list_bars = []

        for row in data.values:
            # Set variables
            date_time = row[0]
            price = np.float(row[1])
            volume = row[2]
            dollar_value = price * volume
            signed_tick = self._apply_tick_rule(price)

            # derivative variables
            price_diff = self._get_price_diff(price)
            log_ret = self._get_log_ret(price)

            self.price_diff.append(price_diff)
            self.trade_size.append(volume)
            self.tick_rule.append(signed_tick)
            self.dollar_size.append(dollar_value)
            self.log_ret.append(log_ret)

            self.prev_price = price

            # If date_time reached bar index
            if date_time >= self.current_date_time:
                self._get_bar_features(date_time, list_bars)

                # Take the next timestamp
                try:
                    self.current_date_time = self.bar_index_iterator.__next__()
                except StopIteration:
                    return list_bars, True  # Looped through all bar index
                # Reset cache
                self._reset_cache()
        return list_bars, False

    def _get_bar_features(self, date_time: pd.Timestamp, list_bars: list) -> list:
        """
        Calculate inter-bar features: lambdas, entropies, avg_tick_size, vwap
        :param date_time: (pd.Timestamp) when bar was formed
        :param list_bars: (list) of previously formed bars
        :return: (list) of inter-bar features
        """
        features = [date_time]

        # Tick rule sum, avg tick size, VWAP
        features.append(get_avg_tick_size(self.trade_size))
        features.append(sum(self.tick_rule))
        features.append(vwap(self.dollar_size, self.trade_size))

        # Lambdas
        features.append(get_trades_based_kyle_lambda(self.price_diff, self.trade_size, self.tick_rule))  # Kyle lambda
        features.append(get_trades_based_amihud_lambda(self.log_ret, self.dollar_size))  # Amihud lambda
        features.append(
            get_trades_based_hasbrouck_lambda(self.log_ret, self.dollar_size, self.tick_rule))  # Hasbrouck lambda

        # Entropy features
        features.append(get_shannon_entropy(encode_tick_rule_array(self.tick_rule)))
        features.append(get_plug_in_entropy(encode_tick_rule_array(self.tick_rule)))
        features.append(get_lempel_ziv_entropy(encode_tick_rule_array(self.tick_rule)))

        if self.volume_encoding is not None:
            message = encode_array(self.trade_size, self.volume_encoding)
            features.append(get_shannon_entropy(message))
            features.append(get_plug_in_entropy(message))
            features.append(get_lempel_ziv_entropy(message))

        if self.pct_encoding is not None:
            message = encode_array(self.log_ret, self.pct_encoding)
            features.append(get_shannon_entropy(message))
            features.append(get_plug_in_entropy(message))
            features.append(get_lempel_ziv_entropy(message))

        list_bars.append(features)

    def _apply_tick_rule(self, price: float) -> int:
        """
        Applies the tick rule as defined on page 29.
        :param price: Price at time t
        :return: The signed tick
        """
        if self.prev_price is not None:
            tick_diff = price - self.prev_price
        else:
            tick_diff = 0

        if tick_diff != 0:
            signed_tick = np.sign(tick_diff)
            self.prev_tick_rule = signed_tick
        else:
            signed_tick = self.prev_tick_rule

        return signed_tick

    def _get_price_diff(self, price: float) -> float:
        """
        Get price difference between ticks

        :param price: Price at time t
        return: price difference
        """
        if self.prev_price is not None:
            price_diff = price - self.prev_price
        else:
            price_diff = 0  # First diff is assumed 0
        return price_diff

    def _get_log_ret(self, price: float) -> float:
        """
        Get log return between ticks

        :param price: Price at time t
        return: log return
        """
        if self.prev_price is not None:
            log_ret = np.log(price / self.prev_price)
        else:
            log_ret = 0  # First return is assumed 0
        return log_ret

    @staticmethod
    def _assert_csv(test_batch):
        """
        Tests that the csv file read has the format: date_time, price, and volume.
        If not then the user needs to create such a file. This format is in place to remove any unwanted overhead.
        :param test_batch: (DataFrame) the first row of the dataset.
        """
        assert test_batch.shape[1] == 3, 'Must have only 3 columns in csv: date_time, price, & volume.'
        assert isinstance(test_batch.iloc[0, 1], float), 'price column in csv not float.'
        assert not isinstance(test_batch.iloc[0, 2], str), 'volume column in csv not int or float.'

        try:
            pd.to_datetime(test_batch.iloc[0, 0])
        except ValueError:
            print('csv file, column 0, not a date time format:',
                  test_batch.iloc[0, 0])