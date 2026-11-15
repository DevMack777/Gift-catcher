import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "gift_catcher.db")

CHECK_INTERVAL = 25          # секунд между проверками
MAX_NEW_PER_CYCLE = 10       # сколько новых номеров максимум забираем за цикл
HTTP_TIMEOUT = 10
PAGE_SIZE = 8
NFT_URL = "https://t.me/nft/{slug}-{number}"

# (код подарка = slug в URL t.me/nft/<slug>-<номер>, отображаемое имя)
# Список редактируйте под нужные коллекции.
COLLECTIONS = [
    ("PlushPepe", "Plush Pepe"),
    ("DurovsCap", "Durov's Cap"),
    ("HeartLocket", "Heart Locket"),
    ("PreciousPeach", "Precious Peach"),
    ("AstralShard", "Astral Shard"),
    ("SwissWatch", "Swiss Watch"),
    ("LootBag", "Loot Bag"),
    ("EternalRose", "Eternal Rose"),
    ("ToyBear", "Toy Bear"),
    ("SharpTongue", "Sharp Tongue"),
]
