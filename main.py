# Souhaib barki
# User story: As a thriftstore reseller
# I want to know how much something from a thrift store is worth on resellplatforms by making a picture and asking ai.
# So that I know if it's profitable to  resell.
from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from PIL import Image
import io
from dotenv import load_dotenv
import os
import google.generativeai as genai
import base64

# Zorgt ervoor dat we de variable gelinkt aan de api key in het .env bestand kunnen gebruiken.
load_dotenv()

# We stellen in met os dat de api key uit de variabele in het .env bestand gelinkt wordt met de api_key parameter.
genai.configure(api_key=os.getenv("MIJN_API_KEY"))

# We maken de webapplicatie.
webapplicatie = FastAPI()

# We linken onze main code met de HTML code die je in de templates folder kan vinden.
templates = Jinja2Templates(directory="templates")


# Functie imported van de Pillow library. Thumbnail Houdt automatisch rekening met de foto ratio.
# Kennelijk kan de AI maar maximaal een foto van 1024 bij 1024 bekijken, vandaar de resize.
def resize_image(image, max_size=(1024, 1024)):
    image.thumbnail(max_size)
    return image

# Functie is een async functie omdat het even kan duren tot de ai een response geeft dus dan kan de code in de tussen tijd wel verder draaien.
# We linken onze gekozen ai (de google ai die foto's kan lezen) met de variabele ai_type.
async def identify_product(image):
    ai_type = genai.GenerativeModel('gemini-1.5-flash')

# We slaan de image data op in een bytes container met gebruik van de IO library en linken het met de variabele genaamd foto_in_bytes.
# Als de image te groot is dan past de resize_image functie het aan en wordt het resultaat gelinkt met de resized_image variabele.
    foto_in_bytes = io.BytesIO()
    resized_image = resize_image(image)
# We slaan de resized foto op in de io.BytesIO() in PNG format.
    resized_image.save(foto_in_bytes, format="PNG")
# We roepen de foto in de bytes container op met de getvalue en vervolgens zetten we het om in een base64 string en die zetten we om in een normale string met .decode().
    foto_verzending = base64.b64encode(foto_in_bytes.getvalue()).decode()
# Dit zijn de prompts die we naar de ai sturen voor de output.
    ai_prompt = ("Identify this product based on the provided images and additional information. "
            "For point 5, provide ONLY the price range with format: $X - $Y. "
            "Provide the following details: 1. Product name 2. Series or brand it belongs to "
            "3. Year of release (if applicable) 4. A brief description 5. An estimated current market price range")
# We vertellen de ai welke foto en wat voor type bestand de foto is.
    image_part = {
        "mime_type": "image/png",
        "data": foto_verzending
    }
# We sturen de prompts en de foto naar de ai zodat de ai weet wat we willen. Vervolgens krijgen we het antwoord in response.text.
    response = ai_type.generate_content([ai_prompt, image_part])
    return response.text

# We vermenigvuldigen de estimated prices met het aantal items van het product.
def calculate_total_prices(product_info, item_count):
    # We zoeken de lijn met de prijsschatting, in de prompt is het beginnend met 5.
    lines = product_info.split('\n')
    for line in lines:
        if line.startswith('5.'):
            # We halen alleen de prijzen eruit.
            price_parts = line.split('$')
            if len(price_parts) >= 3:  # We verwchten tekst voor de prijs quotes.
                min_price_str = price_parts[1].split('-')[0].strip()
                max_price_str = price_parts[2].strip()

                min_price = float(min_price_str.replace(',', '')) # We zetten de string output van de ai om in een float.
                max_price = float(max_price_str.replace(',', ''))

                min_total = min_price * item_count # We vermenigvuldigen de min en max prijs met aantal items.
                max_total = max_price * item_count

                return {
                    "min_total": f"Minimum total price: ${min_total}", #Dictionary met labels. (Total prices)
                    "max_total": f"Maximum total price: ${max_total}",
                    "min_price": min_price
                }

    raise ValueError("Geen prijsschatting")


def is_profitable(bought_price, min_price):
    # We kijken of de bought price minder is dan de minium verkoop prijs
    return bought_price < min_price

# Eerste HTML page die de gebruiker ziet linken.
@webapplicatie.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Input data van de gebruiker (foto, item count en gekochte prijs) functionality
@webapplicatie.post("/upload/")
async def upload_image(
        request: Request,
        file: UploadFile = File(...),
        item_count: int = Form(...),
        bought_price: float = Form(...)
):
    try:
        contents = await file.read() # Leest uploaded bestand (foto van het product)
        image = Image.open(io.BytesIO(contents)) #IO library zorgt dat we de foto byte data kunnen processen met de pillow library (imagine.open).

        product_info = await identify_product(image) #Stuurt de foto naar de identify_product functie

        total_prices = calculate_total_prices(product_info, item_count) # totale prijs uitrekenen.

        min_price = total_prices.get("min_price")
        is_profit = is_profitable(bought_price, min_price) if min_price is not None else None
        profit_message = "Yes, this is profitable to sell" if is_profit else "No, this is not profitable to sell" if is_profit is not None else "No bought price entered"
        # Context dictionary voor de result.html output pagina.
        context = {
            "request": request,
            "product_info": product_info,
            "item_count": item_count,
            "bought_price": bought_price,
            "min_total_price": total_prices["min_total"],
            "max_total_price": total_prices["max_total"],
            "is_profitable": is_profit,
            "profit_message": profit_message
        }
        return templates.TemplateResponse("result.html", context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:webapplicatie", host="127.0.0.1", port=8080, reload=True)
