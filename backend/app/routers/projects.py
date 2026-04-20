from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.models.theme import ProjectTheme, Theme
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schemas.theme import ThemeOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: UUID, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


@router.get("/{project_id}/themes", response_model=List[ThemeOut])
def get_project_themes(project_id: UUID, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    links = db.query(ProjectTheme).filter(ProjectTheme.project_id == project_id).all()
    theme_ids = [link.theme_id for link in links]
    return db.query(Theme).filter(Theme.id.in_(theme_ids)).all()


@router.post("/{project_id}/themes/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_theme_to_project(project_id: UUID, theme_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.get(Theme, theme_id):
        raise HTTPException(status_code=404, detail="Theme not found")
    existing = db.query(ProjectTheme).filter_by(project_id=project_id, theme_id=theme_id).first()
    if not existing:
        db.add(ProjectTheme(project_id=project_id, theme_id=theme_id))
        db.commit()


@router.delete("/{project_id}/themes/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_theme_from_project(project_id: UUID, theme_id: UUID, db: Session = Depends(get_db)):
    link = db.query(ProjectTheme).filter_by(project_id=project_id, theme_id=theme_id).first()
    if link:
        db.delete(link)
        db.commit()
