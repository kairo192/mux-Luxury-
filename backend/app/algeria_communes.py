"""Official commune (baladiya) lists for the 69 Algerian wilayas.

Source: Journal Officiel n° 25 du 5 avril 2026, loi n° 26-06 du 4 avril
2026, which fixes the territorial division at 69 wilayas and 1,541
communes. Commune-to-wilaya assignment and spellings follow that law
(dataset: github.com/riadh2002/algeria-69-wilayas-1541-communes, MIT).

COMMUNES_BY_WILAYA maps the two-digit wilaya code shared by the storefront,
the desktop CMS and the API ("01".."69") to the complete commune list of
that wilaya. The lists are stored in `delivery_zones.communes_json` and feed
the commune selector of the checkout and of the CMS delivery page.

Codes 59-69 are the wilayas created by the 2026 reform: Aflou, Barika,
El Kantara, Bir El Ater, El Aricha, Ksar Chellala, Aïn Ouessara, Messaad,
Ksar El Boukhari, Bou Saâda and El Abiodh Sidi Cheikh.
"""

from typing import Dict, List

COMMUNES_BY_WILAYA: Dict[str, List[str]] = {
    "01": [
        "Adrar", "Akabli", "Aoulef", "Bouda", "Fenoughil", "In Zghmir", "Ouled Ahmed Tammi", "Reggane",
        "Sali", "Sbaa", "Tamentit", "Tamest", "Timokten", "Tit", "Tsabit", "Zaouiet Kounta",
    ],
    "02": [
        "Abou El Hassen", "Ain Merane", "Benairia", "Beni Bouateb", "Beni Haoua", "Beni Rached",
        "Boukadir", "Bouzghaia", "Breira", "Chettia", "Chlef", "Dahra", "El Hadjadj", "El Karimia",
        "El Marsa", "Harchoun", "Herenfa", "Labiod Medjadja", "Moussadek", "Oued Fodda",
        "Oued Goussine", "Oued Sly", "Ouled Abbes", "Ouled Ben Abdelkader", "Ouled Fares", "Oum Drou",
        "Sendjas", "Sidi Abderrahmane", "Sidi Akacha", "Sobha", "Tadjna", "Talassa", "Taougrite",
        "Ténès", "Zeboudja",
    ],
    "03": [
        "Ain Mahdi", "Benacer Ben Chohra", "El Assafia", "El Haouaita", "El Kheneg", "Hassi Delaa",
        "Hassi R'Mel", "Ksar El Hirane", "Laghouat", "Sidi Makhlouf", "Tadjmout", "Tadjrouna",
    ],
    "04": [
        "Ain Babouche", "Aïn Beïda", "Ain Diss", "Ain Fekroune", "Ain Kercha", "Aïn M'lila",
        "Ain Zitoun", "Behir Chergui", "Berriche", "Bir Chouhada", "Dhala", "El Amiria", "El Belala",
        "El Djazia", "El Fedjoudj Boughrara Saoudi", "El Harmilia", "Fkirina", "Hanchir Toumghani",
        "Ksar Sbahi", "Meskiana", "Oued Nini", "Ouled Gacem", "Ouled Hamla", "Ouled Zouai",
        "Oum El Bouaghi", "Rahia", "Sigus", "Souk Naamane", "Zorg",
    ],
    "05": [
        "Ain Djasser", "Aïn Touta", "Ain Yagout", "Arris", "Batna", "Beni Foudhala El Hakania",
        "Boulhilat", "Boumagueur", "Boumia", "Bouzina", "Chemora", "Chir", "Djerma", "El Hassi",
        "El Madher", "Fesdis", "Foum Toub", "Ghassira", "Gosbat", "Guigba", "Hidoussa", "Ichmoul",
        "Inoughissen", "Kimmel", "Ksar Belezma", "Larbaa", "Lazrou", "Lemsane", "Maafa", "Menaa",
        "Merouana", "Ngaous", "Oued Chaaba", "Oued El Ma", "Oued Taga", "Ouled Aouf", "Ouled Fadel",
        "Ouled Selam", "Ouled Si Slimane", "Ouyoun El Assafir", "Rahbat", "Ras El Aioun", "Sefiane",
        "Seriana", "Talkhamt", "Taxlent", "Tazoult", "Teniet El Abed", "Tighanimine", "Tigherghar",
        "Timgad", "Tkout", "Zanat El Beida",
    ],
    "06": [
        "Adekar", "Ait Djellil", "Ait R'zine", "Ait Smail", "Akbou", "Akfadou", "Amalou", "Amizour",
        "Aokas", "Barbacha", "Béjaïa", "Beni Ksila", "Beni Maouch", "Beni Melikeche", "Boudjellil",
        "Bouhamza", "Boukhelifa", "Chelata", "Chemini", "Darguina", "Draa Kaid", "El Kseur",
        "Ferraoun", "Ifelain Ilmathen", "Ighil Ali", "Ighram", "Kendira", "Kherrata", "Leflaye",
        "M'cisna", "Melbou", "Oued Ghir", "Ouzallaguen", "Seddouk", "Semaoun", "Sidi Aich",
        "Sidi Ayad", "Souk El Thenine", "Souk Oufella", "Tala Hamza", "Tamokra", "Tamridjet",
        "Taourirt Ighil", "Taskriout", "Tazmalt", "Thinabdher", "Tibane", "Tichi", "Tifra", "Timzrit",
        "Tizi N'berber", "Toudja",
    ],
    "07": [
        "Ain Naga", "Biskra", "Bordj Ben Azzouz", "Bouchagroun", "Chetma", "El Feidh", "El Ghrous",
        "El Hadjab", "El Haouch", "Foughala", "Khanguet Sidinadji", "Lichana", "Lioua", "M'lili",
        "M'ziraa", "Mchouneche", "Mekhadma", "Oumache", "Ourlal", "Sidi Okba", "Tolga",
        "Zeribet El Oued",
    ],
    "08": [
        "Abadla", "Béchar", "Beni Ounif", "Boukais", "Erg Ferradj", "Kenedsa", "Lahmar",
        "Mechraa Houari Boumedienne", "Meridja", "Mogheul", "Tabalbala", "Taghit",
    ],
    "09": [
        "Ain Romana", "Ben Khlil", "Beni Mered", "Beni Tamou", "Blida", "Bouarfa", "Boufarik",
        "Bougara", "Bouinan", "Chebli", "Chiffa", "Chrea", "Djebabra", "El Affroun", "Guerrouaou",
        "Hammam Melouane", "Larbaa", "Meftah", "Mouzaia", "Oued Djer", "Oued El Alleug",
        "Ouled Selama", "Ouled Yaïch", "Souhane", "Soumaa",
    ],
    "10": [
        "Aghbalou", "Ahl El Ksar", "Ain Bessam", "Aïn El Hadjar", "Ain Laloui", "Ain Turk",
        "Ait Laaziz", "Aomar", "Ath Mansour", "Bechloul", "Bir Ghbalou", "Bordj Oukhriss",
        "Bouderbala", "Bouira", "Boukram", "Chorfa", "Dechmia", "Dirah", "Djebahia", "El Adjiba",
        "El Asnam", "El Hachimia", "El Hakimia", "El Khebouzia", "El Mokrani", "Guerrouma",
        "Hadjera Zerga", "Haizer", "Hanif", "Kadiria", "Lakhdaria", "Maala", "Maamora", "Mchedallah",
        "Mezdour", "Oued El Berdi", "Ouled Rached", "Raouraoua", "Ridane", "Saharidj",
        "Souk El Khemis", "Sour El Ghozlane", "Taghzout", "Taguedit", "Zbarbar",
    ],
    "11": [
        "Abalessa", "Idles", "In Amguel", "Tamanghasset", "Tazouk",
    ],
    "12": [
        "Ain Zerga", "Bedjene", "Bekkaria", "Bir Dheb", "Bir El Mokadem", "Boukhadra", "Boulhaf Dyr",
        "Cheria", "El Aouinet", "El Kouif", "El Ma El Biodh", "El Mazeraa", "El Meridj", "El Ogla",
        "Gorriguer", "Hammamet", "Lahouidjbet", "Morsott", "Ouenza", "Oum Ali", "Safsaf El Ouesra",
        "Stah Guentis", "Tébessa", "Tlidjene",
    ],
    "13": [
        "Ain Fetah", "Ain Fezza", "Ain Ghoraba", "Ain Kebira", "Ain Nehala", "Ain Tallout",
        "Ain Youcef", "Amieur", "Azails", "Bab El Assa", "Beni Bahdel", "Beni Boussaid", "Beni Mester",
        "Beni Ouarsous", "Beni Semiel", "Beni Snous", "Bensekrane", "Bouhlou", "Chetouane",
        "Dar Yaghmouracene", "Djebala", "El Fehoul", "Fellaoucene", "Ghazaouet", "Hammam Boughrara",
        "Hennaya", "Honaine", "Maghnia", "Mansourah", "Marsa Ben Mhidi", "Msirda Fouaga", "Nedroma",
        "Oued Chouly", "Ouled Mimoun", "Ouled Riyah", "Remchi", "Sabra", "Sebbaa Chioukh", "Sebdou",
        "Sidi Abdelli", "Sidi Medjahed", "Souahlia", "Souani", "Souk El Khemis", "Souk Thlata",
        "Terni Beni Hediel", "Tianet", "Tlemcen", "Zenata",
    ],
    "14": [
        "Ain Bouchekif", "Ain Deheb", "Ain El Hadid", "Ain Kermes", "Ain Zarit", "Chehaima",
        "Dahmouni", "Djillali Ben Amar", "Faidja", "Frenda", "Guertoufa", "Madna", "Mahdia",
        "Mechraa Safa", "Medrissa", "Medroussa", "Meghila", "Mellakou", "Nadorah", "Naima",
        "Oued Lilli", "Ouled Djerad", "Rahouia", "Sebaine", "Sebt", "Sidi Abdelghani",
        "Sidi Abderrahmane", "Sidi Ali Mellal", "Sidi Bakhti", "Sidi Hosni", "Sougueur", "Tagdemt",
        "Takhemaret", "Tiaret", "Tidda", "Tousnina",
    ],
    "15": [
        "Abi Youcef", "Aghrib", "Agouni Gueghrane", "Ain El Hammam", "Ain Zaouia", "Ait Aggouacha",
        "Ait Aissa Mimoun", "Ait Bouadou", "Ait Boumehdi", "Ait Chaffaa", "Ait Khelil", "Ait Mahmoud",
        "Ait Oumalou", "Ait Toudert", "Ait Yahia", "Ait Yahia Moussa", "Akbil", "Akerrou",
        "Assi Youcef", "Azazga", "Azzefoun", "Beni Aissi", "Beni Douala", "Beni Yenni", "Beni Ziki",
        "Beni Zmenzer", "Boghni", "Boudjima", "Bounouh", "Bouzguen", "Draâ Ben Khedda",
        "Draa El Mizan", "Freha", "Frikat", "Iboudraren", "Idjeur", "Iferhounene", "Ifigha",
        "Iflissen", "Illilten", "Iloula Oumalou", "Imsouhal", "Irdjen", "Larba Nait Irathen", "Maatka",
        "Makouda", "Mechtrass", "Mekla", "Mizrana", "Mkira", "Ouacif", "Ouadhia", "Ouaguenoun",
        "Sidi Naamane", "Souamaa", "Souk El Thenine", "Tadmait", "Tigzirt", "Timizart", "Tirmitine",
        "Tizi Ghenif", "Tizi Nthlata", "Tizi Ouzou", "Tizi Rached", "Yakouren", "Yatafen", "Zekri",
    ],
    "16": [
        "Ain Benian", "Ain Taya", "Alger Centre", "Bab Azzouar", "Bab El Oued", "Baba Hassen",
        "Bachedjerah", "Baraki", "Belouizdad", "Ben Aknoun", "Beni Messous", "Bir Mourad Rais",
        "Birkhadem", "Birtouta", "Bologhine", "Bordj El Bahri", "Bordj El Kiffan", "Bourouba",
        "Bouzareah", "Casbah", "Chéraga", "Dar El Beida", "Dély Ibrahim", "Djasr Kasentina", "Douera",
        "Draria", "El Achour", "El Biar", "El Hammamet", "El Harrach", "El Madania", "El Magharia",
        "El Mouradia", "Haraoua", "Hussein Dey", "Hydra", "Khracia", "Kouba", "Les Eucalyptus",
        "Mahelma", "Marsa", "Mohammadia", "Oued Koriche", "Oued Smar", "Ouled Chebel", "Ouled Fayet",
        "Rahmania", "Rais Hamidou", "Reghaia", "Rouiba", "Saoula", "Sidi Mhamed", "Sidi Moussa",
        "Souidania", "Staoueli", "Tassala El Merdja", "Zeralda",
    ],
    "17": [
        "Ain Chouhada", "Ain El Ibel", "Ain Maabed", "Beni Yacoub", "Charef", "Dar Chouikh", "Djelfa",
        "Douis", "El Guedid", "El Idrissia", "Hassi Bahbah", "Hassi El Euch", "M'Liliha", "Moudjebara",
        "Sidi Baizid", "Tadmit", "Zaafrane", "Zaccar",
    ],
    "18": [
        "Bordj T'her", "Boudria Beni Yadjis", "Bouraoui Belhadef", "Boussif Ouled Askeur", "Chahna",
        "Chekfa", "Djemaa Beni Habibi", "Djmila", "El Ancer", "El Aouana", "El Kennar Nouchfi",
        "El Milia", "Emir Abdelkader", "Erraguene", "Ghebala", "Jijel", "Kaous", "Kemir Oued Adjoul",
        "Ouadjana", "Ouled Rabah", "Ouled Yahia Khadrouch", "Selma Benziada", "Settara",
        "Sidi Abdelaziz", "Sidi Maarouf", "Taher", "Texena", "Ziamma Mansouriah",
    ],
    "19": [
        "Ain Abessa", "Ain Arnat", "Ain Azal", "Ain El Kebira", "Ain Lahdjar", "Ain Legraj",
        "Ain Oulmane", "Ain Roua", "Ain Sebt", "Ait Naoual Mezada", "Ait Tizi", "Amoucha", "Babor",
        "Bazer Sakhra", "Beidha Bordj", "Belaa", "Beni Aziz", "Beni Chebana", "Beni Fouda",
        "Beni Hocine", "Beni Mouhli", "Beni Ouartilane", "Bir El Arch", "Bir Haddada", "Bouandas",
        "Bougaa", "Bousselam", "Boutaleb", "Dehamcha", "Djemila", "Draa Kebila", "El Eulma",
        "El Ouldja", "El Ouricia", "Guellal", "Guelta Zerka", "Guenzet", "Guidjel", "Hamma",
        "Hammam Essokhna", "Hammam Guergour", "Harbil", "Ksar El Abtal", "Maaouia", "Maouklane",
        "Mezloug", "Oued El Barad", "Ouled Addouane", "Ouled Sabor", "Ouled Sidi Ahmed",
        "Ouled Tebben", "Rosfa", "Salah Bey", "Serdj El Ghoul", "Sétif", "Tachouda", "Talaifacene",
        "Taya", "Tella", "Tizi Nbechar",
    ],
    "20": [
        "Aïn El Hadjar", "Ain Sekhouna", "Ain Soltane", "Doui Thabet", "El Hassasna", "Hounet",
        "Maamora", "Moulay Larbi", "Ouled Brahim", "Ouled Khaled", "Saïda", "Sidi Ahmed", "Sidi Amar",
        "Sidi Boubekeur", "Tircine", "Youb",
    ],
    "21": [
        "Ain Bouziane", "Ain Cherchar", "Ain Kechra", "Ain Zouit", "Azzaba", "Bein El Ouiden",
        "Bekkouche Lakhdar", "Ben Azzouz", "Beni Bachir", "Beni Oulbane", "Beni Zid", "Bouchtata",
        "Cheraia", "Collo", "Djendel", "El Ghedir", "El Hadaik", "El Harrouch", "El Marsa",
        "Emdjez Edchich", "Es Sebt", "Filfila", "Hamadi Krouma", "Kanoua", "Kerkera", "Kheneg Mayoum",
        "Oued Zehour", "Ouldja Boulbalout", "Ouled Attia", "Ouled Hebaba", "Oum Toub",
        "Ramdane Djamel", "Salah Bouchaour", "Sidi Mezghiche", "Skikda", "Tamalous", "Zerdazas",
        "Zitouna",
    ],
    "22": [
        "Ain Adden", "Ain El Berd", "Ain Kada", "Ain Thrid", "Ain Tindamine", "Amarnas",
        "Badredine El Mokrani", "Belarbi", "Ben Badis", "Benachiba Chelia", "Bir El Hammam",
        "Boudjebaa El Bordj", "Boukhanafis", "Chetouane Belaila", "Dhaya", "El Hacaiba", "Hassi Dahou",
        "Hassi Zehana", "Lamtar", "Makedra", "Marhoum", "Mcid", "Merine", "Mezaourou",
        "Mostefa Ben Brahim", "Moulay Slissen", "Oued Sbaa", "Oued Sefioun", "Oued Taourira",
        "Ras El Ma", "Redjem Demouche", "Sehala Thaoura", "Sfissef", "Sidi Ali Benyoub",
        "Sidi Ali Boussidi", "Sidi Bel Abbès", "Sidi Brahim", "Sidi Chaib", "Sidi Dahou",
        "Sidi Hamadouche", "Sidi Khaled", "Sidi Lahcene", "Sidi Yacoub", "Tabia", "Tafissour",
        "Taoudmout", "Teghalimet", "Telagh", "Tenira", "Tessala", "Tilmouni", "Zerouala",
    ],
    "23": [
        "Ain Berda", "Annaba", "Berrahel", "Chetaibi", "Cheurfa", "El Bouni", "El Hadjar", "Eulma",
        "Oued El Aneb", "Seraidi", "Sidi Amer", "Treat",
    ],
    "24": [
        "Ain Ben Beida", "Ain Larbi", "Ain Makhlouf", "Ain Reggada", "Ain Sandel", "Belkhir",
        "Ben Djarah", "Beni Mezline", "Bordj Sabat", "Bou Hachana", "Bou Hamdane", "Bouati Mahmoud",
        "Bouchegouf", "Boumahra Ahmed", "Dahouara", "Djeballah Khemissi", "El Fedjoudj",
        "Guelaat Bou Sbaa", "Guelma", "Hammam Maskhoutine", "Hamman Nbail", "Heliopolis",
        "Houari Boumediene", "Khezara", "Medjez Amar", "Medjez Sfa", "Nechmaya", "Oued Cheham",
        "Oued Fragha", "Oued Zenati", "Ras El Agba", "Roknia", "Salaoua Announa", "Tamlouka",
    ],
    "25": [
        "Ain Abid", "Ain Smara", "Beni Hamiden", "Constantine", "Didouche Mourad", "El Khroub",
        "Hamma Bouziane", "Ibn Badis", "Ibn Ziad", "Mesaoud Boudjeriou", "Ouled Rahmoune",
        "Zighoud Youcef",
    ],
    "26": [
        "Aissaouia", "Baata", "Benchicao", "Beni Slimane", "Berrouaghia", "Bir Ben Laabed",
        "Bouaichoune", "Bouchrahil", "Bouskene", "Deux Bassins", "Djouab", "Draa Essamar", "El Azizia",
        "El Guelbelkebir", "El Hamdania", "El Omaria", "Hannacha", "Khams Djouamaa", "Médéa",
        "Medjebar", "Meghraoua", "Mezerena", "Mihoub", "Ouamri", "Oued Harbil", "Ouled Bouachra",
        "Ouled Brahim", "Ouled Deide", "Ouzera", "Rebaia", "Sedraia", "Seghouane", "Si Mahdjoub",
        "Sidi Errabia", "Sidi Naamane", "Sidi Zahar", "Sidi Ziane", "Souagui", "Tablat", "Tamesguida",
        "Tizi Mahdi", "Tlatet Eddouair", "Zoubiria",
    ],
    "27": [
        "Abdelmalek Ramdane", "Achaacha", "Ain Boudinar", "Ain Nouissy", "Ain Sidi Cherif",
        "Ain Tadles", "Bouguirat", "El Hassiane", "Fornaka", "Hadjadj", "Hassi Maameche", "Khadra",
        "Kheiredine", "Mansourah", "Mesra", "Mezghrane", "Mostaganem", "Nekmaria", "Oued El Kheir",
        "Ouled Boughalem", "Ouled Maallah", "Safsaf", "Sayada", "Sidi Ali", "Sidi Bellater",
        "Sidi Lakhdar", "Sirat", "Souaflia", "Sour", "Stidia", "Tazgait", "Touahria",
    ],
    "28": [
        "Ain El Hadjel", "Ain Khadra", "Belaiba", "Beni Ilmane", "Berhoum", "Bouti Sayah", "Chellal",
        "Dehahna", "Hammam Dhalaa", "Khettouti Sed Djir", "Maadid", "Maarif", "Magra", "Msila",
        "Mtarfa", "Ouanougha", "Ouled Addi Guebala", "Ouled Derradj", "Ouled Madhi", "Ouled Mansour",
        "Sidi Aissa", "Sidi Hadjeres", "Souamaa", "Tarmount",
    ],
    "29": [
        "Ain Fares", "Ain Fekan", "Ain Ferah", "Ain Frass", "Alaimia", "Aouf", "Benian", "Bou Hanifia",
        "Bou Henni", "Chorfa", "El Bordj", "El Gaada", "El Ghomri", "El Hachem", "El Keurt",
        "El Mamounia", "El Menaouer", "Ferraguig", "Froha", "Gharrous", "Gherdjoum", "Ghriss",
        "Guettena", "Hacine", "Khalouia", "Makdha", "Maoussa", "Mascara", "Matemore", "Moctadouz",
        "Mohammadia", "Nesmot", "Oggaz", "Oued El Abtal", "Oued Taria", "Ras Ain Amirouche",
        "Sedjerara", "Sehailia", "Sidi Abdeldjebar", "Sidi Abdelmoumene", "Sidi Boussaid", "Sidi Kada",
        "Sig", "Teghennif", "Tizi", "Zahana", "Zelmata",
    ],
    "30": [
        "Aïn Beïda", "El Borma", "Hassi Ben Abdellah", "Hassi Messaoud", "Ngoussa", "Ouargla",
        "Rouissat", "Sidi Khouiled",
    ],
    "31": [
        "Ain Biya", "Ain Kerma", "Ain Turk", "Arzew", "Ben Freha", "Bethioua", "Bir El Djir",
        "Boufatis", "Bousfer", "Boutlelis", "El Ancar", "El Braya", "El Karma", "Es Senia", "Gdyel",
        "Hassi Ben Okba", "Hassi Bounif", "Hassi Mefsoukh", "Marsat El Hadjadj", "Mers El Kebir",
        "Messerghin", "Oran", "Oued Tlelat", "Sidi Ben Yabka", "Sidi Chami", "Tafraoui",
    ],
    "32": [
        "Boualem", "Bougtoub", "Brezina", "Cheguig", "El Bayadh", "El Kheither", "Ghassoul",
        "Kef El Ahmar", "Krakda", "Rogassa", "Sidi Ameur", "Sidi Slimane", "Sidi Tifour", "Stitten",
        "Tousmouline",
    ],
    "33": [
        "Bordj Omar Driss", "Debdeb", "Illizi", "In Amenas",
    ],
    "34": [
        "Ain Taghrout", "Ain Tesra", "Belimour", "Ben Daoud", "Bir Kasdali", "Bordj Bou Arréridj",
        "Bordj Ghdir", "Bordj Zemoura", "Colla", "Djaafra", "El Ach", "El Achir", "El Anseur",
        "El Hamadia", "El Main", "El Mhir", "Ghilassa", "Haraza", "Hasnaoua", "Khelil", "Ksour",
        "Mansoura", "Medjana", "Ouled Brahem", "Ouled Dahmane", "Ouled Sidi Brahim", "Rabta",
        "Ras El Oued", "Sidi Embarek", "Tafreg", "Taglait", "Teniet En Nasr", "Tesmart", "Tixter",
    ],
    "35": [
        "Afir", "Ammal", "Baghlia", "Ben Choud", "Beni Amrane", "Bordj Menaïel", "Boudouaou",
        "Boudouaou El Bahri", "Boumerdès", "Bouzegza Keddara", "Chabet El Ameur", "Corso", "Dellys",
        "Djinet", "El Kharrouba", "Hammedi", "Isser", "Khemis El Khechna", "Laghata", "Larbatache",
        "Naciria", "Ouled Aissa", "Ouled Hedadj", "Ouled Moussa", "Si Mustapha", "Sidi Daoud",
        "Souk El Had", "Taourga", "Thenia", "Tidjelabine", "Timezrit", "Zemmouri",
    ],
    "36": [
        "Ain El Assel", "Ain Kerma", "Asfour", "Ben Mhidi", "Berrihane", "Besbes", "Bougous",
        "Bouhadjar", "Bouteldja", "Chebaita Mokhtar", "Chefia", "Chihani", "Drean", "Echatt",
        "El Aioun", "El Kala", "El Tarf", "Hammam Beni Salah", "Lac Des Oiseaux", "Oued Zitoun",
        "Raml Souk", "Souarekh", "Zerizer", "Zitouna",
    ],
    "37": [
        "Oum El Assel", "Tindouf",
    ],
    "38": [
        "Ammari", "Beni Chaib", "Beni Lahcene", "Bordj Bou Naama", "Bordj El Emir Abdelkader",
        "Boucaid", "Khemisti", "Larbaa", "Lardjem", "Layoune", "Lazharia", "Maasem", "Melaab",
        "Ouled Bessem", "Sidi Abed", "Sidi Boutouchent", "Sidi Lantri", "Sidi Slimane", "Tamalaht",
        "Theniet El Had", "Tissemsilt", "Youssoufia",
    ],
    "39": [
        "Bayadha", "Beni Guecha", "Debila", "Douar El Ma", "El Ogla", "El Oued", "Guemar", "Hamraia",
        "Hassani Abdelkrim", "Hassi Khelifa", "Kouinine", "Magrane", "Mih Ouansa", "Nakhla",
        "Oued El Alenda", "Ourmas", "Reguiba", "Robbah", "Sidi Aoun", "Taghzout", "Taleb Larbi",
        "Trifaoui",
    ],
    "40": [
        "Ain Touila", "Babar", "Baghai", "Bouhmama", "Chelia", "Cherchar", "Djellal", "El Hamma",
        "El Mahmal", "El Oueldja", "Ensigha", "Kais", "Khenchela", "Khirane", "Msara", "Mtoussa",
        "Ouled Rechache", "Remila", "Tamza", "Taouzianat", "Yabous",
    ],
    "41": [
        "Ain Soltane", "Ain Zana", "Bir Bouhouche", "Drea", "Haddada", "Hanancha", "Khedara",
        "Khemissa", "Mdaourouche", "Mechroha", "Merahna", "Oued Keberit", "Ouled Driss",
        "Ouled Moumen", "Oum El Adhaim", "Quillen", "Ragouba", "Safel El Ouiden", "Sedrata",
        "Sidi Fredj", "Souk Ahras", "Taoura", "Terraguelt", "Tiffech", "Zaarouria", "Zouabi",
    ],
    "42": [
        "Aghbal", "Ahmer El Ain", "Ain Tagourait", "Attatba", "Beni Milleuk", "Bou Haroun",
        "Bou Ismail", "Bourkika", "Chaiba", "Cherchel", "Damous", "Douaouda", "Fouka", "Gouraya",
        "Hadjerat Ennous", "Hadjout", "Khemisti", "Koléa", "Larhat", "Menaceur", "Messelmoun",
        "Meurad", "Nodor", "Sidi Amar", "Sidi Ghiles", "Sidi Rached", "Sidi Semiane", "Tipaza",
    ],
    "43": [
        "Ahmed Rachedi", "Ain Beida Harriche", "Ain Mellouk", "Ain Tine", "Amira Arras",
        "Benyahia Abderrahmane", "Bouhatem", "Chelghoum Laïd", "Chigara", "Derradji Bousselah",
        "El Mechira", "Elayadi Barbes", "Ferdjioua", "Grarem Gouga", "Hamala", "Mila", "Minar Zarza",
        "Oued Athmenia", "Oued Endja", "Oued Seguen", "Ouled Khalouf", "Rouached", "Sidi Khelifa",
        "Sidi Merouane", "Tadjenanet", "Tassadane Haddada", "Telerghma", "Terrai Bainen",
        "Tessala Lamatai", "Tiberguent", "Yahia Beniguecha", "Zeghaia",
    ],
    "44": [
        "Ain Benian", "Ain Bouyahia", "Aïn Defla", "Ain Lechiakh", "Ain Soltane", "Ain Torki", "Arib",
        "Barbouche", "Bathia", "Belaas", "Ben Allal", "Bir Ouled Khelifa", "Bordj Emir Khaled",
        "Boumedfaa", "Bourached", "Djelida", "Djemaa Ouled Chikh", "Djendel", "El Abadia", "El Amra",
        "El Attaf", "El Hassania", "El Maine", "Hammam Righa", "Hoceinia", "Khemis Miliana",
        "Mekhatria", "Miliana", "Oued Chorfa", "Oued Djemaa", "Rouina", "Sidi Lakhdar",
        "Tachta Zegagha", "Tarik Ibn Ziad", "Tiberkanine", "Zeddine",
    ],
    "45": [
        "Ain Ben Khelil", "Aïn Sefra", "Assela", "Djeniane Bourzeg", "El Biod", "Kasdir",
        "Makman Ben Amer", "Mechria", "Moghrar", "Naâma", "Sfissifa", "Tiout",
    ],
    "46": [
        "Aghlal", "Ain El Arbaa", "Ain Kihal", "Aïn Témouchent", "Ain Tolba", "Aoubellil", "Beni Saf",
        "Bou Zedjar", "Chaabet El Ham", "Chentouf", "El Amria", "El Emir Abdelkader", "El Malah",
        "El Messaid", "Hammam Bouhadjar", "Hassasna", "Hassi El Ghella", "Oued Berkeche", "Oued Sabah",
        "Ouled Boudjemaa", "Ouled Kihal", "Oulhaca El Gheraba", "Sidi Ben Adda", "Sidi Boumediene",
        "Sidi Ouriache", "Sidi Safi", "Tamzoura", "Terga",
    ],
    "47": [
        "Berriane", "Bounoura", "Dhayet Bendhahoua", "El Atteuf", "El Guerrara", "Ghardaïa",
        "Mansoura", "Metlili", "Sebseb", "Zelfana",
    ],
    "48": [
        "Ain Rahma", "Ain Tarek", "Ammi Moussa", "Belaassel Bouzegza", "Bendaoud", "Beni Dergoun",
        "Beni Zentis", "Dar Ben Abdellah", "Djidiouia", "El Guettar", "El Hamadna", "El Hassi",
        "El Matmar", "El Ouldja", "Had Echkalla", "Hamri", "Kalaa", "Lahlef", "Mazouna", "Mediouna",
        "Mendes", "Merdja Sidi Abed", "Ouarizane", "Oued El Djemaa", "Oued Essalem", "Oued Rhiou",
        "Ouled Aiche", "Ouled Sidi Mihoub", "Ramka", "Relizane", "Sidi Khettab", "Sidi Lazreg",
        "Sidi Mhamed Ben Ali", "Sidi Mhamed Ben Aouda", "Sidi Saada", "Souk El Haad", "Yellel",
        "Zemmoura",
    ],
    "49": [
        "Aougrout", "Charouine", "Deldoul", "Ksar Kaddour", "Metarfa", "Ouled Aissa", "Ouled Said",
        "Talmine", "Timimoun", "Tinerkouk",
    ],
    "50": [
        "Bordj Badji Mokhtar", "Timiaouine",
    ],
    "51": [
        "Besbes", "Doucen", "Ech Chaiba", "Ouled Djellal", "Ras El Miaad", "Sidi Khaled",
    ],
    "52": [
        "Béni Abbès", "Beni Ikhlef", "El Ouata", "Igli", "Kerzaz", "Ksabi", "Ouled Khoudir", "Tamtert",
        "Timoudi",
    ],
    "53": [
        "Foggaret Ezzaouia", "In Ghar", "In Salah",
    ],
    "54": [
        "In Guezzam", "Tinzaouatine",
    ],
    "55": [
        "Balidat Ameur", "Benaceur", "El Allia", "El Hadjira", "Megarine", "Mnaguer", "Nezla",
        "Sidi Slimane", "Taibet", "Tamacine", "Tebesbest", "Touggourt", "Zaouia El Abidia",
    ],
    "56": [
        "Bordj El Haouasse", "Djanet",
    ],
    "57": [
        "Djamaa", "El Mghair", "Mrara", "Oum Touyour", "Sidi Amrane", "Sidi Khellil", "Still",
        "Tendla",
    ],
    "58": [
        "El Meniaa", "Hassi Fehal", "Hassi Gara",
    ],
    "59": [
        "Aflou", "Ain Sidi Ali", "Beidha", "Brida", "El Ghicha", "Gueltat Sidi Saad", "Hadj Mechri",
        "Oued M'Zi", "Oued Morra", "Sebgag", "Sidi Bouzid", "Taouiala",
    ],
    "60": [
        "Barika", "Bitam", "Djezzar", "M'doukel", "Metkaouak", "Ouled Ammar", "Seggana", "Tilatou",
    ],
    "61": [
        "Aïn Zaatout", "Branis", "Djemorah", "El Kantara", "El Outaya",
    ],
    "62": [
        "Bir El Ater", "El Ogla", "Ferkane", "Negrine",
    ],
    "63": [
        "El Aricha", "El Bouihi", "El Gor", "Sidi Djillali",
    ],
    "64": [
        "Bougara", "Hamadia", "Ksar Chellala", "Rechaiga", "Serghine", "Zmalet El Emir Aek",
    ],
    "65": [
        "Ain Fekka", "Aïn Oussera", "Benhar", "Birine", "Bouira Lahdeb", "El Khemis", "Guernini",
        "Had Sahary", "Hassi Fedoul", "Sidi Ladjel",
    ],
    "66": [
        "Amourah", "Deldoul", "Feidh El Botma", "Guettara", "Messaad", "Oum Laadham", "Sed Rahal",
        "Selmana",
    ],
    "67": [
        "Ain Boucif", "Ain Ouksir", "Aziz", "Boghar", "Bouaiche", "Boughezoul", "Chahbounia",
        "Chelalet El Adhaoura", "Cheniguel", "Derrag", "El Ouinet", "Kef Lakhdar", "Ksar El Boukhari",
        "Meftaha", "Ouled Antar", "Ouled Hellal", "Ouled Maaref", "Oum El Djalil", "Saneg",
        "Sidi Damed", "Tafraout",
    ],
    "68": [
        "Ain El Melh", "Ain Errich", "Ain Fares", "Ben Srour", "Benzouh", "Bir Foda", "Bou Saâda",
        "Djebel Messaad", "El Hamel", "El Houamed", "Khoubana", "M'cif", "Medjedel", "Oued Chair",
        "Ouled Atia", "Ouled Sidi Brahim", "Ouled Slimane", "Oultene", "Sidi Ameur", "Sidi Mhamed",
        "Slim", "Tamsa", "Zarzour",
    ],
    "69": [
        "Ain El Orak", "Arbaouat", "Boussemghoun", "Chellala", "El Abiodh Sidi Cheikh", "El Bnoud",
        "El Mehara",
    ],
}

# 1,541 communes in total (loi n° 26-06, art. 3).
TOTAL_COMMUNES: int = sum(len(names) for names in COMMUNES_BY_WILAYA.values())
