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

public class JavaAgent {
    private Jira jira;
    private Project project;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;

    public JavaAgent(Jira jira, Project project, FieldManager fieldManager, CustomFieldManager customFieldManager) {
        this.jira = jira;
        this.project = project;
        this.fieldManager = fieldManager;
        this.customFieldManager = customFieldManager;
    }

    public void logActivity(String activity) throws JiraException {
        Issue issue = createIssue("Java Activity", activity);
        updateFields(issue, "Description", activity);
    }

    private Issue createIssue(String summary, String description) throws JiraException {
        Project project = jira.getProject(project.getKey());
        TextField descriptionField = (TextField) fieldManager.getFieldByName("description");
        UserPickerField assigneeField = (UserPickerField) fieldManager.getFieldByName("assignee");

        return jira.createIssue(
            project.getKey(),
            summary,
            descriptionField,
            assigneeField
        );
    }

    private void updateFields(Issue issue, String fieldName, String value) throws JiraException {
        SelectField selectField = (SelectField) fieldManager.getFieldByName(fieldName);
        SelectOptions options = selectField.getOptions();
        SelectOption selectedOption = null;

        for (SelectOption option : options) {
            if (option.getValue().equals(value)) {
                selectedOption = option;
                break;
            }
        }

        if (selectedOption != null) {
            jira.updateIssue(issue.getId(), issue, new HashMap<>());
        } else {
            throw new JiraException("Option not found");
        }
    }

    public static void main(String[] args) throws Exception {
        // Configuração do Jira
        Jira jira = new Jira();
        Project project = jira.getProjectByKey("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        JavaAgent agent = new JavaAgent(jira, project, fieldManager, customFieldManager);

        // Exemplo de uso
        agent.logActivity("New feature implemented");
    }
}