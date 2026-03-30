from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GlobalRole(str, Enum):
    editor = "editor"
    admin = "admin"


class MembershipRole(str, Enum):
    editor = "editor"
    organization_admin = "organization_admin"


class RepositoryProvider(str, Enum):
    local = "local"
    github = "github"
    gitlab = "gitlab"


class Visibility(str, Enum):
    private = "private"
    public = "public"


class ReviewKind(str, Enum):
    issue = "issue"
    pull_request = "pull_request"


class ReviewStatus(str, Enum):
    open = "open"
    draft = "draft"
    merged = "merged"
    closed = "closed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    global_role: Mapped[GlobalRole] = mapped_column(
        SqlEnum(GlobalRole),
        default=GlobalRole.editor,
    )
    auth_provider: Mapped[str] = mapped_column(String(50), default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    owned_books: Mapped[list["Book"]] = relationship(back_populates="owner")


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    repository_sources: Mapped[list["RepositorySource"]] = relationship(
        back_populates="organization"
    )
    books: Mapped[list["Book"]] = relationship(back_populates="organization")


class OrganizationMembership(TimestampMixin, Base):
    __tablename__ = "organization_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    role: Mapped[MembershipRole] = mapped_column(SqlEnum(MembershipRole))

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class RepositorySource(TimestampMixin, Base):
    __tablename__ = "repository_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[RepositoryProvider] = mapped_column(SqlEnum(RepositoryProvider))
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    provider_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    repository_namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repository_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    organization: Mapped[Organization | None] = relationship(back_populates="repository_sources")
    books: Mapped[list["Book"]] = relationship(back_populates="repository_source")


class Book(TimestampMixin, Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    course: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(SqlEnum(Visibility), default=Visibility.private)
    repository_source_id: Mapped[int] = mapped_column(ForeignKey("repository_sources.id"))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    base_branch: Mapped[str] = mapped_column(String(255), default="main")
    content_path: Mapped[str] = mapped_column(String(1024))
    assets_path: Mapped[str] = mapped_column(String(1024))

    repository_source: Mapped[RepositorySource] = relationship(back_populates="books")
    organization: Mapped[Organization | None] = relationship(back_populates="books")
    owner: Mapped[User | None] = relationship(back_populates="owned_books")
    comments: Mapped[list["BookComment"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )
    review_requests: Mapped[list["ReviewRequest"]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
    )


class BookComment(TimestampMixin, Base):
    __tablename__ = "book_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    branch_name: Mapped[str] = mapped_column(String(255))
    anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text)

    book: Mapped[Book] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class ReviewRequest(TimestampMixin, Base):
    __tablename__ = "review_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    repo_source_id: Mapped[int] = mapped_column(ForeignKey("repository_sources.id"))
    kind: Mapped[ReviewKind] = mapped_column(SqlEnum(ReviewKind))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    base_branch: Mapped[str] = mapped_column(String(255))
    head_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(SqlEnum(ReviewStatus), default=ReviewStatus.open)
    external_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    book: Mapped[Book] = relationship(back_populates="review_requests")
    repository_source: Mapped[RepositorySource] = relationship()
