import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import requests

def _parse_csv_line(line):
    fields = []
    current = []
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            fields.append(''.join(current))
            current = []
        else:
            current.append(char)
    fields.append(''.join(current))
    return fields

def _check_header(first_line, expected_columns, source_name):
    actual_columns = [
        col.strip().strip('"').lower()
        for col in _parse_csv_line(first_line.strip())
    ]
    expected_lower = [col.lower() for col in expected_columns]
    if actual_columns != expected_lower:
        raise ValueError(
            f'Unexpected file structure for {source_name}: '
            f'expected header {expected_columns}, got {actual_columns}'
        )

def _mean(values):
    return sum(values) / len(values)


def _median(values):
    ordered = sorted(values)
    size = len(ordered)
    middle = size // 2
    if size % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _variance(values):
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return sum((item - mean) ** 2 for item in values) / len(values)


def _metric_func(metric):
    if metric in ('average', 'mean'):
        return _mean
    if metric == 'median':
        return _median
    raise ValueError(f'Unknown metric: {metric}')


def _load_movie_titles(ratings_path):
    titles = {}
    movies_path = os.path.join(os.path.dirname(ratings_path), 'movies.csv')
    try:
        with open(movies_path, encoding='utf-8') as file:
            file.readline()
            for line in file:
                parts = _parse_csv_line(line.strip())
                if len(parts) < 3:
                    continue
                try:
                    titles[int(parts[0])] = parts[1]
                except ValueError:
                    continue
    except OSError:
        return titles
    return titles


class Movies:
    EXPECTED_HEADER = ['movieId', 'title', 'genres']

    def __init__(self, path_to_the_file):
        self.movies = []
        try:
            with open(path_to_the_file, encoding='utf-8') as file:
                header = file.readline()
                _check_header(header, self.EXPECTED_HEADER, path_to_the_file)
                for i, line in enumerate(file):
                    if i >= 1000:
                        break
                    parts = _parse_csv_line(line.strip())
                    if len(parts) < 3:
                        continue
                    try:
                        movie_id = int(parts[0])
                    except ValueError:
                        continue
                    self.movies.append({
                        'movieId': movie_id,
                        'title': parts[1],
                        'genres': parts[2],
                    })
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {path_to_the_file}')
        except OSError as error:
            raise OSError(f'Cannot read file: {error}')
        if not self.movies:
            raise ValueError(f'No valid movies in file: {path_to_the_file}')

    def dist_by_release(self):
        """
        Метод возвращает словарь, где ключи - годы, а значения - количество фильмов.
        Сортирует по убыванию количества.
        """
        years = []
        for movie in self.movies:
            match = re.search(r'\((\d{4})\)\s*$', movie['title'])
            if match:
                years.append(int(match.group(1)))
        counts = Counter(years)
        return dict(
            sorted(counts.items(), key=lambda item: item[1], reverse=True)
        )

    def dist_by_genres(self):
        """
        Метод возвращает словарь, где ключи - жанры, а значения - количество фильмов.
        Сортирует по убыванию количества.
        """
        genres = []
        for movie in self.movies:
            if movie['genres'] == '(no genres listed)':
                continue
            genres.extend(movie['genres'].split('|'))

        counts = Counter(genres)
        return dict(
            sorted(counts.items(), key=lambda item: item[1], reverse=True)
        )

    def most_genres(self, n):
        """
        Метод возвращает словарь с top-n фильмами, где ключи - названия фильмов,
        а значения - количество жанров у фильма. Сортирует по убыванию чисел.
        """
        result = {}
        for movie in self.movies:
            title = movie['title']
            genres = movie['genres']

            if genres == '(no genres listed)':
                num = 0
            else:
                num = len(genres.split('|'))
            result[title] = num

        sorted_items = sorted(
            result.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        return dict(sorted_items[:n])


class Tags:
    EXPECTED_HEADER = ['userId', 'movieId', 'tag', 'timestamp']
    def __init__(self, path_to_the_file):
        self.tags = []
        try:
            with open(path_to_the_file, encoding='utf-8') as file:
                header = file.readline()
                _check_header(header, self.EXPECTED_HEADER, path_to_the_file)
                for i, line in enumerate(file):
                    if i >= 1000:
                        break
                    parts = _parse_csv_line(line.strip())
                    if len(parts) < 4:
                        continue
                    try:
                        self.tags.append({
                            'userId': int(parts[0]),
                            'movieId': int(parts[1]),
                            'tag': parts[2],
                            'timestamp': int(parts[3]),
                        })
                    except ValueError:
                        continue
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {path_to_the_file}')
        except OSError as error:
            raise OSError(f'Cannot read file: {error}')
        if not self.tags:
            raise ValueError(f'No valid tags in file: {path_to_the_file}')

    def most_words(self, n):
        """Метод возвращает top-n тегов с наибольшим количеством слов внутри. 
        Ключи - теги, а значения - количество слов внутри тега.
         Сортирует по убыванию чисел.
        """
        unique_tags = set(row['tag'] for row in self.tags)
        words_count = {}
        for tag in unique_tags:
            words_count[tag] = len(tag.split())
        sorted_items = sorted(
            words_count.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        return dict(sorted_items[:n])

    def longest(self, n):
        """
        Метод возвращает top-n самых длинных тегов по количеству символов.
        Сортирует по убыванию чисел.
        """
        unique_tags = set(row['tag'] for row in self.tags)
        sorted_tags = sorted(unique_tags, key=len, reverse=True)
        return sorted_tags[:n]

    def most_words_and_longest(self, n):
        """
        Метод возвращает пересечение между top-n тегами с наибольшим количеством слов внутри и
        top-n самыми длинными тегами по количеству символов.
        """
        by_words = set(self.most_words(n).keys())
        by_length = set(self.longest(n))
        return list(by_words & by_length)

    def most_popular(self, n):
        """
        Метод возвращает самые популярные теги.
        Ключи - теги, а значения - количество упоминаний.
        Сортирует по убыванию количества упоминаний.
        """
        all_tags = [row['tag'] for row in self.tags]
        counts = Counter(all_tags)
        sorted_items = sorted(
            counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        return dict(sorted_items[:n])

    def tags_with(self, word):
        """
        Метод возвращает все уникальные теги, которые содержат слово, переданное в качестве аргумента.
        Сортирует по алфавиту по названиям тегов.
        """
        unique_tags = set(row['tag'] for row in self.tags)
        pattern = re.compile(
            r'\b' + re.escape(word) + r'\b',
            flags=re.IGNORECASE,
        )
        matched = [tag for tag in unique_tags if pattern.search(tag)]
        return sorted(matched)


class Ratings:
    EXPECTED_HEADER = ['userId', 'movieId', 'rating', 'timestamp']
    def __init__(self, path_to_the_file):
        self.ratings = []
        try:
            with open(path_to_the_file, encoding='utf-8') as file:
                header = file.readline()
                _check_header(header, self.EXPECTED_HEADER, path_to_the_file)
                for i, line in enumerate(file):
                    if i >= 1000:
                        break
                    parts = _parse_csv_line(line.strip())
                    if len(parts) < 4:
                        continue
                    try:
                        self.ratings.append({
                            'userId': int(parts[0]),
                            'movieId': int(parts[1]),
                            'rating': float(parts[2]),
                            'timestamp': int(parts[3]),
                        })
                    except ValueError:
                        continue
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {path_to_the_file}')
        except OSError as error:
            raise OSError(f'Cannot read file: {error}')
        if not self.ratings:
            raise ValueError(f'No valid ratings in file: {path_to_the_file}')

        movie_titles = _load_movie_titles(path_to_the_file)
        self.movies = self.Movies(self.ratings, movie_titles)
        self.users = self.Users(self.ratings)

    class Movies:
        def __init__(self, ratings, movie_titles=None):
            self.ratings = ratings
            self.movie_titles = movie_titles or {}
            self._group_key = 'movieId'

        def _group_ratings(self):
            groups = {}
            for row in self.ratings:
                key = row[self._group_key]
                groups.setdefault(key, []).append(row['rating'])
            return groups

        def _title(self, movie_id):
            return self.movie_titles.get(movie_id, str(movie_id))

        def dist_by_year(self):
            """
            Метод возвращает словарь, где ключи - годы, а значения - количество оценок.
            Сортирует по возрастанию лет.
            """
            years = []
            for row in self.ratings:
                year = datetime.fromtimestamp(
                    row['timestamp'],
                    tz=timezone.utc,
                ).year
                years.append(year)
            counts = Counter(years)
            return dict(sorted(counts.items(), key=lambda item: item[0]))

        def dist_by_rating(self):
            """
            Метод возвращает словарь, где ключи - оценки, а значения - количество оценок.
            Сортирует по возрастанию оценок.
            """
            values = [row['rating'] for row in self.ratings]
            counts = Counter(values)
            return dict(sorted(counts.items(), key=lambda item: item[0]))

        def top_by_num_of_ratings(self, n):
            """
            Метод возвращает top-n фильмов по количеству оценок.
            Ключи - названия фильмов, а значения - количество оценок.
            Сортирует по убыванию чисел.
            """
            groups = self._group_ratings()
            counts = {
                self._title(movie_id): len(ratings)
                for movie_id, ratings in groups.items()
            }
            sorted_items = sorted(
                counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            return dict(sorted_items[:n])

        def top_by_ratings(self, n, metric='average'):
            """
            Метод возвращает top-n фильмов по среднему или медианному значению оценок.
            Это словарь, где ключи - названия фильмов, а значения - метрические значения.
            Сортирует по убыванию метрики.
            Значения должны быть округлены до 2 знаков после запятой.
            """
            func = _metric_func(metric)
            groups = self._group_ratings()
            scores = {}
            for movie_id, ratings in groups.items():
                scores[self._title(movie_id)] = round(func(ratings), 2)
            sorted_items = sorted(
                scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            return dict(sorted_items[:n])

        def top_controversial(self, n):
            """
            Метод возвращает top-n фильмов по дисперсии оценок.
            Это словарь, где ключи - названия фильмов, а значения - дисперсии.
            Сортирует по убыванию дисперсии.
            Значения должны быть округлены до 2 знаков после запятой.
            """
            groups = self._group_ratings()
            scores = {}
            for movie_id, ratings in groups.items():
                if len(ratings) < 2:
                    continue
                scores[self._title(movie_id)] = round(_variance(ratings), 2)
            sorted_items = sorted(
                scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            return dict(sorted_items[:n])

    class Users(Movies):
        """
        В этом классе должны работать три метода.
        1-й возвращает распределение пользователей по количеству оценок, которые они поставили.
        2-й возвращает распределение пользователей по среднему или медианному значению их оценок.
        3-й возвращает top-n пользователей с наибольшей дисперсией их оценок.
        Наследуется от класса Movies. Некоторые методы аналогичны методам из него.
        """
        def __init__(self, ratings):
            super().__init__(ratings)
            self._group_key = 'userId'

        def dist_by_num_of_ratings(self):
            groups = self._group_ratings()
            counts = Counter(len(ratings) for ratings in groups.values())
            return dict(sorted(counts.items(), key=lambda item: item[0]))

        def dist_by_ratings(self, metric='average'):
            func = _metric_func(metric)
            groups = self._group_ratings()
            scores = [
                round(func(ratings), 2) for ratings in groups.values()
            ]
            counts = Counter(scores)
            return dict(sorted(counts.items(), key=lambda item: item[0]))

        def top_controversial(self, n):
            groups = self._group_ratings()
            scores = {}
            for user_id, ratings in groups.items():
                if len(ratings) < 2:
                    continue
                scores[user_id] = round(_variance(ratings), 2)
            sorted_items = sorted(
                scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            return dict(sorted_items[:n])

class Links:
    EXPECTED_HEADER = ['movieId', 'imdbId', 'tmdbId']
    def __init__(
        self,
        path_to_links_csv: str,
        path_to_movies_csv: str = None,
        tmdb_api_token: str = None,
    ):
        self.path_to_links_csv = path_to_links_csv
        self.path_to_movies_csv = path_to_movies_csv

        self.api_token = tmdb_api_token or os.environ.get('TMDB_API_TOKEN', '')
 
        self.base_url = "https://shrill-breeze-8a39.daria-shchupakova1.workers.dev/3"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "accept": "application/json",
        }
        self.cache_file = "tmdb_cache.json"
 
        self.links = self._read_links()
        self.movies_dict = self._read_movies()
        self._tmdb_by_movie = {
            item["movieId"]: item["tmdbId"] for item in self.links
        }
 
        for item in self.links:
            m_id = item["movieId"]
            item["title"] = self.movies_dict.get(m_id, f"Movie {m_id}")
 
        self.imdb_data = self._load_or_fetch_tmdb()
 
    def _read_links(self):
        links_data = []
        try:
            with open(self.path_to_links_csv, "r", encoding="utf-8") as f:
                header = f.readline()
                _check_header(header, self.EXPECTED_HEADER, self.path_to_links_csv)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        links_data.append({
                            "movieId": parts[0].strip().strip('"'),
                            "imdbId": parts[1].strip().strip('"'),
                            "tmdbId": parts[2].strip().strip('"'),
                        })
                    if len(links_data) == 1000:
                        break
        except FileNotFoundError:
            raise FileNotFoundError(f'File not found: {self.path_to_links_csv}')
        except OSError as error:
            raise OSError(f'Cannot read file: {error}')
        if not links_data:
            raise ValueError(
                f'No valid links in file: {self.path_to_links_csv}')
        return links_data
 
    def _read_movies(self):
        movies_dict = {}
        if not self.path_to_movies_csv or not os.path.exists(
            self.path_to_movies_csv
        ):
            return movies_dict
 
        target_ids = {item["movieId"] for item in self.links}
        with open(self.path_to_movies_csv, "r", encoding="utf-8") as f:
            f.readline()
            for line in f:
                line = line.strip()
                if line:
                    first_comma = line.find(",")
                    last_comma = line.rfind(",")
                    if (
                        first_comma != -1
                        and last_comma != -1
                        and first_comma < last_comma
                    ):
                        movie_id = line[:first_comma].strip().strip('"')
                        if movie_id in target_ids:
                            title = line[first_comma + 1: last_comma].strip().strip('"')
                            movies_dict[movie_id] = title
        return movies_dict
 
    def _extract_data(self, json_data):
        director = "Unknown"
        crew = json_data.get("credits", {}).get("crew", [])
        for member in crew:
            if member.get("job") == "Director":
                director = member.get("name", "Unknown")
                break
 
        return {
            "director": director,
            "Director": director,
            "budget": float(json_data.get("budget", 0.0) or 0.0),
            "Budget": float(json_data.get("budget", 0.0) or 0.0),
            "gross": float(json_data.get("revenue", 0.0) or 0.0),
            "Cumulative Worldwide Gross": float(
                json_data.get("revenue", 0.0) or 0.0
            ),
            "runtime": int(json_data.get("runtime") or 0),
            "Runtime": int(json_data.get("runtime") or 0),
        }
 
    def _default_movie_data(self):
        return {
            "director": "Unknown",
            "Director": "Unknown",
            "budget": 0.0,
            "Budget": 0.0,
            "gross": 0.0,
            "Cumulative Worldwide Gross": 0.0,
            "runtime": 0,
            "Runtime": 0,
        }
 
    def _fetch_one(self, tmdb_id):
        """Один запрос к TMDB. Любая сетевая/HTTP ошибка возвращаются данные по умолчанию."""
        url = f"{self.base_url}/movie/{tmdb_id}"
        params = {"language": "en-US", "append_to_response": "credits"}
 
        target = datetime.now() + timedelta(milliseconds=250)
        while datetime.now() < target:
            pass
 
        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=5
            )
            response.raise_for_status()
            return self._extract_data(response.json())
        except (requests.exceptions.RequestException, ValueError):
            return self._default_movie_data()
 
    def _load_or_fetch_tmdb(self):
        data = {}
 
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
 
        updated = False
        for item in self.links:
            movie_id = str(item["movieId"])
            tmdb_id = item.get("tmdbId")
 
            if movie_id in data:
                continue
 
            if not tmdb_id:
                data[movie_id] = self._default_movie_data()
            else:
                data[movie_id] = self._fetch_one(tmdb_id)
 
            updated = True
 
        if updated or not os.path.exists(self.cache_file):
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
 
        return data
 
    def get_movie_details(self, tmdb_id):
        """Данные по конкретному tmdbId."""
        movie_id = None
        for item in self.links:
            if item.get("tmdbId") == str(tmdb_id):
                movie_id = item["movieId"]
                break
        if movie_id is None:
            return self._default_movie_data()
        if movie_id not in self.imdb_data:
            self.imdb_data[movie_id] = self._fetch_one(tmdb_id)
        return self.imdb_data[movie_id]
 
    def get_imdb(self, list_of_movies, list_of_fields):
        """
        Метод возвращает список списков [movieId, поле1, поле2, поле3, ...] для списка фильмов,
        переданного в качестве аргумента (movieId).
        Например, [movieId, Режиссёр, Бюджет, Совокупные мировые кассовые сборы, Продолжительность].
        Сортирует по убыванию movieId.
        """
        sorted_movie_ids = sorted(
            list_of_movies, key=lambda x: int(x), reverse=True
        )
        result = []
        for m_id in sorted_movie_ids:
            str_id = str(m_id)
 
            if str_id not in self.imdb_data:
                tmdb_id = self._tmdb_by_movie.get(str_id)
                if not tmdb_id:
                    self.imdb_data[str_id] = self._default_movie_data()
                else:
                    self.imdb_data[str_id] = self._fetch_one(tmdb_id)
 
            info = self.imdb_data[str_id]
            row = [m_id]
            for field in list_of_fields:
                val = info.get(field)
                if val is None:
                    val = info.get(str(field).lower())
                row.append(val)
            result.append(row)
        return result
 
    def top_directors(self, n = 5):
        """
        Метод возвращает словарь с top-n режиссёрами, где ключи - режиссёры,
        а значения - количество созданных ими фильмов. Сортирует по убыванию чисел.
        """
        directors_count = {}
        for movie in self.imdb_data.values():
            d = movie.get("director", "Unknown")
            if d != "Unknown":
                directors_count[d] = directors_count.get(d, 0) + 1
        sorted_directors = sorted(
            directors_count.items(), key=lambda x: x[1], reverse=True
        )[:n]
        return dict(sorted_directors)
 
    def most_expensive(self, n = 5):
        """
        Метод возвращает словарь с top-n фильмами, где ключи - названия фильмов,
        а значения - их бюджеты. Сортирует по убыванию бюджетов.
        """
        movies = {}
        for item in self.links:
            m_id = item["movieId"]
            title = item["title"]
            if m_id in self.imdb_data:
                movies[title] = self.imdb_data[m_id]["budget"]
        sorted_movies = sorted(movies.items(), key=lambda x: x[1], reverse=True)[:n]
        return dict(sorted_movies)
 
    def most_profitable(self, n = 5):
        """
        Метод возвращает словарь с top-n фильмами, где ключи - названия фильмов,
        а значения - разница между совокупными мировыми кассовыми сборами и бюджетом.
        Сортирует по убыванию разницы.
        """
        movies = {}
        for item in self.links:
            m_id = item["movieId"]
            title = item["title"]
            if m_id in self.imdb_data:
                info = self.imdb_data[m_id]
                movies[title] = info["gross"] - info["budget"]
        sorted_movies = sorted(movies.items(), key=lambda x: x[1], reverse=True)[:n]
        return dict(sorted_movies)
 
    def longest(self, n = 5):
        """
        Метод возвращает словарь с top-n фильмами, где ключи - названия фильмов,
        а значения - их продолжительность. 
        Сортирует по убыванию продолжительности.
        """
        movies = {}
        for item in self.links:
            m_id = item["movieId"]
            title = item["title"]
            if m_id in self.imdb_data:
                movies[title] = self.imdb_data[m_id]["runtime"]
        sorted_movies = sorted(movies.items(), key=lambda x: x[1], reverse=True)[:n]
        return dict(sorted_movies)
 
    def top_cost_per_minute(self, n = 5):
        """
        Метод возвращает словарь с top-n фильмами, где ключи - названия фильмов,
        а значения - бюджет, разделённый на их продолжительность.
        Значения должны быть округлены до 2 знаков после запятой. Сортирует по убыванию частного.
        """
        movies = {}
        for item in self.links:
            m_id = item["movieId"]
            title = item["title"]
            if m_id in self.imdb_data:
                info = self.imdb_data[m_id]
                if info["runtime"] > 0:
                    movies[title] = round(info["budget"] / info["runtime"], 2)
                else:
                    movies[title] = 0.0
        sorted_movies = sorted(movies.items(), key=lambda x: x[1], reverse=True)[:n]
        return dict(sorted_movies)
 
 
class Tests:
    @classmethod
    def setup_class(cls):
        # Все csv лежат в той же папке, что и сам модуль/тесты.
        base = os.path.dirname(os.path.abspath(__file__))
        cls.movies = Movies(os.path.join(base, 'movies.csv'))
        cls.tags = Tags(os.path.join(base, 'tags.csv'))
        cls.ratings = Ratings(os.path.join(base, 'ratings.csv'))
        cls.rating_movies = cls.ratings.movies
        cls.users = cls.ratings.users
        cls.links = Links(
            os.path.join(base, 'links.csv'),
            os.path.join(base, 'movies.csv'),
        )
 
    def test_dist_by_release_type(self):
        result = self.movies.dist_by_release()
        assert isinstance(result, dict)
 
    def test_dist_by_release_inner_types(self):
        result = self.movies.dist_by_release()
        for year, count in result.items():
            assert isinstance(year, int)
            assert isinstance(count, int)
 
    def test_dist_by_release_sorted(self):
        result = self.movies.dist_by_release()
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_dist_by_genres_type(self):
        result = self.movies.dist_by_genres()
        assert isinstance(result, dict)
 
    def test_dist_by_genres_inner_types(self):
        result = self.movies.dist_by_genres()
        for genre, count in result.items():
            assert isinstance(genre, str)
            assert isinstance(count, int)
 
    def test_dist_by_genres_sorted(self):
        result = self.movies.dist_by_genres()
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_most_genres_type(self):
        result = self.movies.most_genres(10)
        assert isinstance(result, dict)
 
    def test_most_genres_inner_types(self):
        result = self.movies.most_genres(10)
        for title, num in result.items():
            assert isinstance(title, str)
            assert isinstance(num, int)
 
    def test_most_genres_length(self):
        n = 10
        result = self.movies.most_genres(n)
        assert len(result) == n
 
    def test_most_genres_sorted(self):
        result = self.movies.most_genres(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_most_words_type(self):
        result = self.tags.most_words(10)
        assert isinstance(result, dict)
 
    def test_most_words_inner_types(self):
        result = self.tags.most_words(10)
        for tag, count in result.items():
            assert isinstance(tag, str)
            assert isinstance(count, int)
 
    def test_most_words_length(self):
        n = 10
        result = self.tags.most_words(n)
        assert len(result) == n
 
    def test_most_words_sorted(self):
        result = self.tags.most_words(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_longest_type(self):
        result = self.tags.longest(10)
        assert isinstance(result, list)
 
    def test_longest_inner_types(self):
        result = self.tags.longest(10)
        for tag in result:
            assert isinstance(tag, str)
 
    def test_longest_length(self):
        n = 10
        result = self.tags.longest(n)
        assert len(result) == n
 
    def test_longest_sorted(self):
        result = self.tags.longest(10)
        lengths = [len(tag) for tag in result]
        assert lengths == sorted(lengths, reverse=True)
 
    def test_most_words_and_longest_type(self):
        result = self.tags.most_words_and_longest(10)
        assert isinstance(result, list)
 
    def test_most_words_and_longest_inner_types(self):
        result = self.tags.most_words_and_longest(10)
        for tag in result:
            assert isinstance(tag, str)
 
    def test_most_words_and_longest_is_intersection(self):
        n = 10
        result = self.tags.most_words_and_longest(n)
        by_words = set(self.tags.most_words(n).keys())
        by_length = set(self.tags.longest(n))
        assert set(result) == (by_words & by_length)
 
    def test_most_popular_type(self):
        result = self.tags.most_popular(10)
        assert isinstance(result, dict)
 
    def test_most_popular_inner_types(self):
        result = self.tags.most_popular(10)
        for tag, count in result.items():
            assert isinstance(tag, str)
            assert isinstance(count, int)
 
    def test_most_popular_length(self):
        n = 10
        result = self.tags.most_popular(n)
        assert len(result) == n
 
    def test_most_popular_sorted(self):
        result = self.tags.most_popular(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_tags_with_type(self):
        result = self.tags.tags_with('fun')
        assert isinstance(result, list)
 
    def test_tags_with_inner_types(self):
        result = self.tags.tags_with('fun')
        for tag in result:
            assert isinstance(tag, str)
 
    def test_tags_with_contains_word(self):
        word = 'fun'
        result = self.tags.tags_with(word)
        pattern = re.compile(
            r'\b' + re.escape(word) + r'\b',
            flags=re.IGNORECASE,
        )
        for tag in result:
            assert pattern.search(tag)
 
    def test_tags_with_whole_word(self):
        result = self.tags.tags_with('fun')
        assert 'funny' not in result
        assert 'fun family movie' in result
        assert result == self.tags.tags_with('FUN')
 
    def test_tags_with_sorted(self):
        result = self.tags.tags_with('fun')
        assert result == sorted(result)
 
    def test_dist_by_year_type(self):
        result = self.rating_movies.dist_by_year()
        assert isinstance(result, dict)
 
    def test_dist_by_year_inner_types(self):
        result = self.rating_movies.dist_by_year()
        for year, count in result.items():
            assert isinstance(year, int)
            assert isinstance(count, int)
 
    def test_dist_by_year_sorted(self):
        result = self.rating_movies.dist_by_year()
        years = list(result.keys())
        assert years == sorted(years)
 
    def test_dist_by_rating_type(self):
        result = self.rating_movies.dist_by_rating()
        assert isinstance(result, dict)
 
    def test_dist_by_rating_inner_types(self):
        result = self.rating_movies.dist_by_rating()
        for rating, count in result.items():
            assert isinstance(rating, float)
            assert isinstance(count, int)
 
    def test_dist_by_rating_sorted(self):
        result = self.rating_movies.dist_by_rating()
        ratings = list(result.keys())
        assert ratings == sorted(ratings)
 
    def test_top_by_num_of_ratings_type(self):
        result = self.rating_movies.top_by_num_of_ratings(10)
        assert isinstance(result, dict)
 
    def test_top_by_num_of_ratings_inner_types(self):
        result = self.rating_movies.top_by_num_of_ratings(10)
        for title, count in result.items():
            assert isinstance(title, str)
            assert isinstance(count, int)
 
    def test_top_by_num_of_ratings_length(self):
        n = 10
        result = self.rating_movies.top_by_num_of_ratings(n)
        assert len(result) == n
 
    def test_top_by_num_of_ratings_sorted(self):
        result = self.rating_movies.top_by_num_of_ratings(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_top_by_ratings_type(self):
        result = self.rating_movies.top_by_ratings(10)
        assert isinstance(result, dict)
 
    def test_top_by_ratings_inner_types(self):
        result = self.rating_movies.top_by_ratings(10)
        for title, score in result.items():
            assert isinstance(title, str)
            assert isinstance(score, float)
 
    def test_top_by_ratings_length(self):
        n = 10
        result = self.rating_movies.top_by_ratings(n)
        assert len(result) == n
 
    def test_top_by_ratings_sorted(self):
        result = self.rating_movies.top_by_ratings(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_top_by_ratings_median_sorted(self):
        result = self.rating_movies.top_by_ratings(10, metric='median')
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_top_controversial_type(self):
        result = self.rating_movies.top_controversial(10)
        assert isinstance(result, dict)
 
    def test_top_controversial_inner_types(self):
        result = self.rating_movies.top_controversial(10)
        for title, score in result.items():
            assert isinstance(title, str)
            assert isinstance(score, float)
 
    def test_top_controversial_length(self):
        n = 10
        result = self.rating_movies.top_controversial(n)
        assert len(result) == n
 
    def test_top_controversial_sorted(self):
        result = self.rating_movies.top_controversial(10)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_users_dist_by_num_of_ratings_type(self):
        result = self.users.dist_by_num_of_ratings()
        assert isinstance(result, dict)
 
    def test_users_dist_by_num_of_ratings_inner_types(self):
        result = self.users.dist_by_num_of_ratings()
        for num_ratings, num_users in result.items():
            assert isinstance(num_ratings, int)
            assert isinstance(num_users, int)
 
    def test_users_dist_by_num_of_ratings_sorted(self):
        result = self.users.dist_by_num_of_ratings()
        keys = list(result.keys())
        assert keys == sorted(keys)
 
    def test_users_dist_by_ratings_type(self):
        result = self.users.dist_by_ratings()
        assert isinstance(result, dict)
 
    def test_users_dist_by_ratings_inner_types(self):
        result = self.users.dist_by_ratings()
        for score, num_users in result.items():
            assert isinstance(score, float)
            assert isinstance(num_users, int)
 
    def test_users_dist_by_ratings_sorted(self):
        result = self.users.dist_by_ratings()
        keys = list(result.keys())
        assert keys == sorted(keys)
 
    def test_users_top_controversial_type(self):
        result = self.users.top_controversial(5)
        assert isinstance(result, dict)
 
    def test_users_top_controversial_inner_types(self):
        result = self.users.top_controversial(5)
        for user_id, score in result.items():
            assert isinstance(user_id, int)
            assert isinstance(score, float)
 
    def test_users_top_controversial_sorted(self):
        result = self.users.top_controversial(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_get_imdb_type(self):
        result = self.links.get_imdb([1, 2], ['Director', 'Budget'])
        assert isinstance(result, list)
 
    def test_get_imdb_inner_types(self):
        result = self.links.get_imdb([1, 2], ['Director', 'Budget'])
        for row in result:
            assert isinstance(row, list)
            assert isinstance(row[0], (int, str))
 
    def test_get_imdb_sorted(self):
        result = self.links.get_imdb([1, 2, 3], ['Director'])
        movie_ids = [int(row[0]) for row in result]
        assert movie_ids == sorted(movie_ids, reverse=True)
 
    def test_get_imdb_handles_request_errors(self):
        broken_links = Links(
            self.links.path_to_links_csv,
            self.links.path_to_movies_csv,
            tmdb_api_token='definitely-invalid-token',
        )
        broken_links.imdb_data = {}
        result = broken_links.get_imdb([1], ['Director'])
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0][0] == 1
 
    def test_top_directors_type(self):
        result = self.links.top_directors(5)
        assert isinstance(result, dict)
 
    def test_top_directors_sorted(self):
        result = self.links.top_directors(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_most_expensive_type(self):
        result = self.links.most_expensive(5)
        assert isinstance(result, dict)
 
    def test_most_expensive_sorted(self):
        result = self.links.most_expensive(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_most_profitable_type(self):
        result = self.links.most_profitable(5)
        assert isinstance(result, dict)
 
    def test_most_profitable_sorted(self):
        result = self.links.most_profitable(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_links_longest_type(self):
        result = self.links.longest(5)
        assert isinstance(result, dict)
 
    def test_links_longest_sorted(self):
        result = self.links.longest(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)
 
    def test_top_cost_per_minute_type(self):
        result = self.links.top_cost_per_minute(5)
        assert isinstance(result, dict)
 
    def test_top_cost_per_minute_sorted(self):
        result = self.links.top_cost_per_minute(5)
        values = list(result.values())
        assert values == sorted(values, reverse=True)