"""Write zero-shot schemas for the English and social-media datasets (descriptions follow each dataset's
annotation guidelines; examples are made up, not taken from the data)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "schemas"

CROSSNER = {
    "person": ("person", "a person who does not fit a more specific role type listed here", ["John Smith"]),
    "politician": ("politician", "a person active in politics: head of state, minister, legislator, party leader", ["Angela Merkel"]),
    "writer": ("writer", "a person known as an author, novelist, poet or playwright", ["Jane Austen"]),
    "scientist": ("scientist", "a person known as a scientist", ["Marie Curie"]),
    "researcher": ("researcher", "a person known for research in AI or computer science", ["Geoffrey Hinton"]),
    "musicalartist": ("musical artist", "a singer, musician, composer or rapper", ["Adele"]),
    "organisation": ("organisation", "an organisation, company, agency, court, army or institution that fits no more specific type", ["Red Cross", "Google"]),
    "politicalparty": ("political party", "a political party", ["Labour Party"]),
    "university": ("university", "a university or college", ["Stanford University"]),
    "band": ("band", "a musical group or band", ["The Beatles"]),
    "country": ("country", "a country or nation state, including historical ones", ["France", "Soviet Union"]),
    "location": ("location", "a geographic place that is not a country: city, region, province, river, mountain, constituency", ["Paris", "Ontario"]),
    "election": ("election", "a named election", ["2010 UK general election"]),
    "event": ("event", "a named event such as a war, festival, conference or ceremony", ["World War II", "Woodstock"]),
    "award": ("award", "a named award, prize or honour", ["Nobel Prize in Physics", "Grammy Award"]),
    "book": ("book", "title of a book or novel", ["Pride and Prejudice"]),
    "poem": ("poem", "title of a poem", ["The Raven"]),
    "magazine": ("magazine", "a magazine, newspaper or periodical", ["The New Yorker"]),
    "literarygenre": ("literary genre", "a genre of literature", ["science fiction", "poetry"]),
    "album": ("album", "title of a music album", ["Abbey Road"]),
    "song": ("song", "title of a song or single", ["Yesterday"]),
    "musicgenre": ("music genre", "a genre of music", ["jazz", "hip hop"]),
    "musicalinstrument": ("musical instrument", "a musical instrument", ["guitar", "violin"]),
    "field": ("field", "a research field or subfield", ["machine learning", "computer vision"]),
    "task": ("task", "a problem or task studied in AI", ["machine translation", "image classification"]),
    "algorithm": ("algorithm", "an algorithm, model or method", ["gradient descent", "support vector machine"]),
    "metrics": ("metrics", "an evaluation metric or measure", ["F1 score", "BLEU"]),
    "product": ("product", "a product, software system or tool", ["iPhone", "TensorFlow"]),
    "programlang": ("programming language", "a programming language", ["Python", "Lisp"]),
    "conference": ("conference", "an academic conference or journal venue", ["NeurIPS", "ICML"]),
    "discipline": ("discipline", "an academic discipline", ["physics", "biochemistry"]),
    "theory": ("theory", "a named scientific theory, law or principle", ["general relativity"]),
    "academicjournal": ("academic journal", "an academic journal", ["Nature", "Physical Review Letters"]),
    "astronomicalobject": ("astronomical object", "a planet, star, galaxy, comet or other celestial object", ["Mars", "Andromeda Galaxy"]),
    "chemicalelement": ("chemical element", "a chemical element", ["oxygen", "iron"]),
    "chemicalcompound": ("chemical compound", "a chemical compound or molecule", ["glucose", "sodium chloride"]),
    "enzyme": ("enzyme", "an enzyme", ["lactase", "DNA polymerase"]),
    "protein": ("protein", "a protein that is not an enzyme", ["hemoglobin", "insulin"]),
    "misc": ("miscellaneous", "any other named entity that fits none of the types above, e.g. nationality, language, religion, named object or work", ["German", "Buddhism"]),
}

DOMAINS = {
    "ai": ["algorithm", "conference", "country", "field", "location", "metrics", "misc", "organisation", "person", "product", "programlang", "researcher", "task", "university"],
    "literature": ["award", "book", "country", "event", "literarygenre", "location", "magazine", "misc", "organisation", "person", "poem", "writer"],
    "music": ["album", "award", "band", "country", "event", "location", "misc", "musicalartist", "musicalinstrument", "musicgenre", "organisation", "person", "song"],
    "politics": ["country", "election", "event", "location", "misc", "organisation", "person", "politicalparty", "politician"],
    "science": ["academicjournal", "astronomicalobject", "award", "chemicalcompound", "chemicalelement", "country", "discipline", "enzyme", "event", "location", "misc", "organisation", "person", "protein", "scientist", "theory", "university"],
}

OTHERS = {
    "wnut": {
        "person": ("person", "name of a person, including usernames or nicknames that refer to a person", ["Taylor", "Jonyeee"]),
        "location": ("location", "name of a place: city, country, venue, landmark", ["Chicago", "Central Park"]),
        "corporation": ("corporation", "a company or business named as an organisation", ["Apple", "Starbucks"]),
        "product": ("product", "a named product, device, app, game or service", ["Galaxy S8", "Instagram"]),
        "creative_work": ("creative work", "title of a movie, song, book, TV show or album", ["Game of Thrones"]),
        "group": ("group", "a named group: band, sports team, club, political or social group", ["Lakers", "Metallica"]),
    },
    "mitres": {
        "restaurant_name": ("restaurant name", "name of a restaurant or chain", ["olive garden"]),
        "cuisine": ("cuisine", "a type of cuisine or restaurant category", ["thai", "fast food"]),
        "dish": ("dish", "a specific dish, food or drink", ["pad thai", "margaritas"]),
        "amenity": ("amenity", "a feature or service of the place: seating, parking, bar, kid friendly, atmosphere", ["outdoor seating", "kid friendly"]),
        "location": ("location", "where the restaurant should be, including relative phrases", ["near me", "within 5 miles", "downtown"]),
        "hours": ("hours", "opening time or time constraint", ["open now", "after 10 pm"]),
        "price": ("price", "price level or cost words", ["cheap", "under 20 dollars"]),
        "rating": ("rating", "quality or rating words", ["five star", "highly rated"]),
    },
    "weibo": {
        "per_nam": ("人名", "具体人物的名字、昵称或艺名", ["刘德华", "小明"]),
        "per_nom": ("人物泛指", "指人的普通名词或称呼，如亲属、身份、群体", ["男朋友", "网友", "美女"]),
        "org_nam": ("机构名", "具体公司、学校、团体、品牌主体的名称", ["小米", "北京大学"]),
        "org_nom": ("机构泛指", "指机构的普通名词", ["公司", "学校", "政府"]),
        "gpe_nam": ("行政区名", "国家、省、市、县等行政区划名称", ["中国", "广州"]),
        "gpe_nom": ("行政区泛指", "指行政区划的普通名词", ["国家", "城市", "家乡"]),
        "loc_nam": ("地点名", "具体地点、景点、建筑、自然地理名称", ["西湖", "天安门"]),
        "loc_nom": ("地点泛指", "指地点的普通名词", ["公园", "机场", "楼下"]),
    },
}


def spec(title: str, desc: str, examples: list[str]) -> dict:
    return {"title": title, "description": desc, "examples": examples}


def main() -> None:
    for dom, types in DOMAINS.items():
        schema = {"entities": {t: spec(*CROSSNER[t]) for t in types}}
        (OUT / f"crossner_{dom}.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, types in OTHERS.items():
        schema = {"entities": {t: spec(*v) for t, v in types.items()}}
        if name == "weibo":
            for t in ("per_nam",):
                schema["entities"][t]["min_chars"] = 1
        (OUT / f"{name}.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(sorted(p.name for p in OUT.glob("*.json")))


if __name__ == "__main__":
    main()
