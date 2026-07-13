from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import conjugate
from app.deps import chapter_or_404, get_conn

router = APIRouter(prefix="/api/verbs")

PERSONS = ["yo", "tu", "el", "nosotros", "vosotros", "ellos"]


class Forms(BaseModel):
    yo: str = Field(min_length=1)
    tu: str = Field(min_length=1)
    el: str = Field(min_length=1)
    nosotros: str = Field(min_length=1)
    vosotros: str = Field(min_length=1)
    ellos: str = Field(min_length=1)


class VerbIn(BaseModel):
    chapter_id: int
    infinitive_es: str = Field(min_length=1)
    translation_nl: str = Field(min_length=1)
    tense: str = "presente"
    forms: Forms


class VerbUpdate(BaseModel):
    infinitive_es: str = Field(min_length=1)
    translation_nl: str = Field(min_length=1)
    tense: str = "presente"
    forms: Forms


def _save_forms(conn, verb_id, tense, forms):
    conn.execute(
        "DELETE FROM conjugations WHERE verb_id = ? AND tense = ?", (verb_id, tense)
    )
    for person in PERSONS:
        conn.execute(
            "INSERT INTO conjugations (verb_id, tense, person, form) "
            "VALUES (?, ?, ?, ?)",
            (verb_id, tense, person, getattr(forms, person).strip()),
        )


@router.get("")
def list_verbs(chapter_id: int, conn=Depends(get_conn)):
    verbs = {
        row["id"]: dict(row, conjugations={})
        for row in conn.execute(
            "SELECT id, chapter_id, infinitive_es, translation_nl FROM verbs "
            "WHERE chapter_id = ? ORDER BY id",
            (chapter_id,),
        )
    }
    if verbs:
        placeholders = ",".join("?" * len(verbs))
        for row in conn.execute(
            f"SELECT verb_id, tense, person, form FROM conjugations "
            f"WHERE verb_id IN ({placeholders})",
            list(verbs),
        ):
            verbs[row["verb_id"]]["conjugations"].setdefault(row["tense"], {})[
                row["person"]
            ] = row["form"]
    return list(verbs.values())


@router.get("/conjugate")
def conjugate_verb(infinitive: str):
    try:
        forms = conjugate.lookup_presente(infinitive.strip().lower())
    except conjugate.SourceUnavailable:
        raise HTTPException(status_code=503, detail="Wiktionary is niet bereikbaar")
    if not forms:
        raise HTTPException(
            status_code=404,
            detail=f"Geen vervoegingen gevonden voor '{infinitive.strip()}'",
        )
    return {"tense": "presente", "forms": forms}


@router.post("", status_code=201)
def create_verb(body: VerbIn, conn=Depends(get_conn)):
    chapter_or_404(conn, body.chapter_id)
    cursor = conn.execute(
        "INSERT INTO verbs (chapter_id, infinitive_es, translation_nl) "
        "VALUES (?, ?, ?)",
        (body.chapter_id, body.infinitive_es.strip(), body.translation_nl.strip()),
    )
    _save_forms(conn, cursor.lastrowid, body.tense, body.forms)
    conn.commit()
    return {"id": cursor.lastrowid}


@router.put("/{verb_id}")
def update_verb(verb_id: int, body: VerbUpdate, conn=Depends(get_conn)):
    cursor = conn.execute(
        "UPDATE verbs SET infinitive_es = ?, translation_nl = ? WHERE id = ?",
        (body.infinitive_es.strip(), body.translation_nl.strip(), verb_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Werkwoord niet gevonden")
    _save_forms(conn, verb_id, body.tense, body.forms)
    conn.commit()
    return {"id": verb_id}


@router.delete("/{verb_id}", status_code=204)
def delete_verb(verb_id: int, conn=Depends(get_conn)):
    cursor = conn.execute("DELETE FROM verbs WHERE id = ?", (verb_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Werkwoord niet gevonden")
