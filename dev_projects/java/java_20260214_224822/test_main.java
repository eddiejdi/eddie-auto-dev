import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.select.SelectField;
import com.atlassian.jira.issue.fields.select.SelectOption;
import com.atlassian.jira.issue.fields.select.SelectOptions;
import com.atlassian.jira.issue.fields.select.SelectValue;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Test;

public class JavaAgentTest {

    @Test
    public void testLogActivity() throws JiraException {
        // Configuração do Jira
        Jira jira = new Jira();
        Project project = jira.getProjectByKey("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        JavaAgent agent = new JavaAgent(jira, project, fieldManager, customFieldManager);

        // Caso de sucesso com valores válidos
        agent.logActivity("New feature implemented");
    }

    @Test
    public void testLogActivityWithInvalidValue() throws JiraException {
        // Configuração do Jira
        Jira jira = new Jira();
        Project project = jira.getProjectByKey("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        JavaAgent agent = new JavaAgent(jira, project, fieldManager, customFieldManager);

        // Caso de erro (divisão por zero)
        assertThrows(JiraException.class, () -> agent.logActivity("New feature implemented"));
    }

    @Test
    public void testLogActivityWithInvalidFieldName() throws JiraException {
        // Configuração do Jira
        Jira jira = new Jira();
        Project project = jira.getProjectByKey("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        JavaAgent agent = new JavaAgent(jira, project, fieldManager, customFieldManager);

        // Caso de erro (campo inválido)
        assertThrows(JiraException.class, () -> agent.logActivity("New feature implemented", "InvalidFieldName"));
    }
}