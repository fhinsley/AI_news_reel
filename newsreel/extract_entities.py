import spacy
import config

def extract_entities(script_file):
    nlp = spacy.load("en_core_web_sm")
    
    with open(script_file, "r") as f:
        text = f.read()
    
    doc = nlp(text)
    
    entities = {}
    for ent in doc.ents:
        # Skip short or generic entities
        if len(ent.text) < 3:
            continue
        # Skip break tags and script formatting
        if ent.text.startswith("<"):
            continue
        
        # Group by entity type
        if ent.label_ not in entities:
            entities[ent.label_] = set()
        entities[ent.label_].add(ent.text)
    
    return entities

if __name__ == "__main__":
    entities = extract_entities(config.EL_INPUT_FILE)
    for label, names in sorted(entities.items()):
        print(f"\n{label}:")
        for name in sorted(names):
            print(f"  {name}")