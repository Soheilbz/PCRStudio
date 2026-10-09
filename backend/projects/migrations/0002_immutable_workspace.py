from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql="""
        CREATE FUNCTION pcrstudio_project_workspace_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.workspace_id IS DISTINCT FROM NEW.workspace_id THEN
            RAISE EXCEPTION USING ERRCODE = '23514', MESSAGE = 'project_workspace_immutable';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER project_workspace_immutable
        BEFORE UPDATE ON projects_project
        FOR EACH ROW EXECUTE FUNCTION pcrstudio_project_workspace_guard();
        """,
            reverse_sql="""
        DROP TRIGGER project_workspace_immutable ON projects_project;
        DROP FUNCTION pcrstudio_project_workspace_guard();
        """,
        )
    ]
