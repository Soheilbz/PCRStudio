from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("workspaces", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql="""
        CREATE FUNCTION pcrstudio_membership_identity_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
             OR OLD.user_id IS DISTINCT FROM NEW.user_id
             OR (OLD.active = false AND NEW.active = true) THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'membership_identity_immutable';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER membership_identity_immutable
        BEFORE UPDATE ON workspaces_membership
        FOR EACH ROW EXECUTE FUNCTION pcrstudio_membership_identity_guard();
        """,
            reverse_sql="""
        DROP TRIGGER membership_identity_immutable ON workspaces_membership;
        DROP FUNCTION pcrstudio_membership_identity_guard();
        """,
        )
    ]
