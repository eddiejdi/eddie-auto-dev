import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try (Jira jira = new Jira(jiraUrl, username, password)) {

            // Obter o Projeto
            Project project = jira.getProject("YOUR_PROJECT_KEY");

            // Obter o CustomFieldManager
            FieldManager fieldManager = jira.getFieldManager();

            // Criar um novo campo customizado para tracking de atividades
            CustomFieldManager customFieldManager = jira.getCustomFieldManager();
            String customFieldName = "Tracking Activity";
            com.atlassian.jira.issue.customfields.CustomFieldType customFieldType = customFieldManager.getCustomFieldTypeByName("Text");
            if (customFieldType != null) {
                com.atlassian.jira.issue.fields.CustomField customField = fieldManager.createCustomField(customFieldName, customFieldType);
            }

            // Criar uma nova Issue
            String issueKey = "YOUR_ISSUE_KEY";
            Issue issue = jira.getIssue(issueKey);

            // Adicionar um novo campo customizado à Issue
            TextField trackingActivityField = (TextField) customFieldManager.getFieldByName("Tracking Activity");
            if (trackingActivityField != null) {
                issue.addCustomFieldValue(trackingActivityField, "In progress");
            }

        } catch (JiraException e) {
            e.printStackTrace();
        }
    }
}