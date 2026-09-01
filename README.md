# HoopPro prototipas

## Paleidimas
1. Įsidiekite Python 3.10+.
2. Terminale:
   python -m venv .venv
   - Windows: .venv\Scripts\activate
   - macOS/Linux: source .venv/bin/activate
3. `pip install -r requirements.txt`
4. `python app.py`
5. Naršyklėje atidarykite `http://127.0.0.1:5000`

## Demo administratoriaus paskyra
El. paštas: `admin@hooppro.lt`
Slaptažodis: `Admin123!`

Prototipas automatiškai sukuria SQLite duomenų bazę ir tris pavyzdines treniruotes.

## Įdiegta
- Žaidėjo paskyros kūrimas ir prisijungimas
- Treniruotės su vietų limitu
- Registracija į treniruotę
- Registracijos atšaukimas
- Mano registracijų puslapis
- Administratoriaus skydas
- Treniruočių kūrimas / trynimas
- Žaidėjų sąrašas
- Slaptažodžių hash'inimas

Tai yra lokalus MVP prototipas. Viešam naudojimui dar reikėtų HTTPS, CSRF apsaugos, saugaus SECRET_KEY, el. pašto patvirtinimo / slaptažodžio atkūrimo, GDPR dokumentacijos ir produkcinės DB.
