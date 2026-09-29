from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "436482c3bd63"
down_revision: Union[str, None] = "2daec0f4da6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "user_server_access",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(), nullable=False, server_default="read"),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "server_id"),
    )
    op.create_index(
        "ix_user_server_access_user_id", "user_server_access", ["user_id"], unique=False
    )
    op.create_index(
        "ix_user_server_access_server_id", "user_server_access", ["server_id"], unique=False
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("anomaly_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("reconstruction_error", sa.Float(), nullable=False, server_default="0"),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0"),
        sa.Column("shap_explanation", sa.JSON(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_anomalies_id"), "anomalies", ["id"], unique=False)
    op.create_index(op.f("ix_anomalies_server_id"), "anomalies", ["server_id"], unique=False)
    op.create_index(op.f("ix_anomalies_detected_at"), "anomalies", ["detected_at"], unique=False)
    op.create_index(op.f("ix_anomalies_anomaly_type"), "anomalies", ["anomaly_type"], unique=False)
    op.create_index(op.f("ix_anomalies_severity"), "anomalies", ["severity"], unique=False)
    op.create_index(op.f("ix_anomalies_status"), "anomalies", ["status"], unique=False)
    op.create_index(
        "ix_anomalies_server_detected",
        "anomalies",
        ["server_id", "detected_at"],
        unique=False,
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("anomaly_id", sa.Integer(), nullable=False),
        sa.Column("llm_raw_output", sa.Text(), nullable=True),
        sa.Column("filtered_command", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["anomaly_id"], ["anomalies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recommendations_id"), "recommendations", ["id"], unique=False)
    op.create_index(
        op.f("ix_recommendations_anomaly_id"), "recommendations", ["anomaly_id"], unique=False
    )
    op.create_index(
        op.f("ix_recommendations_status"), "recommendations", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_recommendations_created_at"), "recommendations", ["created_at"], unique=False
    )

    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_channels_id"), "notification_channels", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_notification_channels_user_id"),
        "notification_channels",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_channels_channel_type"),
        "notification_channels",
        ["channel_type"],
        unique=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("anomaly_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("channels_sent", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["anomaly_id"], ["anomalies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_notifications_anomaly_id"), "notifications", ["anomaly_id"], unique=False
    )
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_notifications_sent_at"), "notifications", ["sent_at"], unique=False)
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(op.f("ix_refresh_tokens_jti"), "refresh_tokens", ["jti"], unique=False)
    op.create_index(
        op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_revoked"), "refresh_tokens", ["revoked"], unique=False
    )

def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_revoked"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_jti"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index(op.f("ix_notifications_sent_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_anomaly_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(
        op.f("ix_notification_channels_channel_type"), table_name="notification_channels"
    )
    op.drop_index(op.f("ix_notification_channels_user_id"), table_name="notification_channels")
    op.drop_index(op.f("ix_notification_channels_id"), table_name="notification_channels")
    op.drop_table("notification_channels")

    op.drop_index(op.f("ix_recommendations_created_at"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_status"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_anomaly_id"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_id"), table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_anomalies_server_detected", table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_status"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_severity"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_anomaly_type"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_detected_at"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_server_id"), table_name="anomalies")
    op.drop_index(op.f("ix_anomalies_id"), table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_user_server_access_server_id", table_name="user_server_access")
    op.drop_index("ix_user_server_access_user_id", table_name="user_server_access")
    op.drop_table("user_server_access")
