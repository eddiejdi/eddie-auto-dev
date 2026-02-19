import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.DateField;
import com.atlassian.jira.issue.fields.NumberField;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.SelectField;
import com.atlassian.jira.issue.fields.MultipleSelectField;
import com.atlassian.jira.issue.fields.BooleanField;
import com.atlassian.jira.issue.fields.AttachmentField;
import com.atlassian.jira.issue.fields.CustomFieldType;
import com.atlassian.jira.issue.fields.FieldType;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.DateField;
import com.atlassian.jira.issue.fields.NumberField;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.SelectField;
import com.atlassian.jira.issue.fields.MultipleSelectField;
import com.atlassian.jira.issue.fields.BooleanField;
import com.atlassian.jira.issue.fields.AttachmentField;

public class JavaAgent {

    private Jira jira;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;

    public JavaAgent(Jira jira, FieldManager fieldManager, CustomFieldManager customFieldManager) {
        this.jira = jira;
        this.fieldManager = fieldManager;
        this.customFieldManager = customFieldManager;
    }

    public void registerEvent(String issueKey, String eventType, String eventData) {
        try {
            Issue issue = jira.getIssue(issueKey);
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: " + issueKey);
            }
            CustomField eventField = customFieldManager.getCustomFieldByName("Event");
            if (eventField == null) {
                throw new IllegalArgumentException("Event field not found");
            }
            TextField textField = (TextField) eventField.getFieldObject();
            textField.setValue(issue, eventData);
        } catch (Exception e) {
            System.err.println("Error registering event: " + e.getMessage());
        }
    }

    public void monitorActivity(String issueKey, String activityType, String activityData) {
        try {
            Issue issue = jira.getIssue(issueKey);
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: " + issueKey);
            }
            CustomField activityField = customFieldManager.getCustomFieldByName("Activity");
            if (activityField == null) {
                throw new IllegalArgumentException("Activity field not found");
            }
            TextField textField = (TextField) activityField.getFieldObject();
            textField.setValue(issue, activityData);
        } catch (Exception e) {
            System.err.println("Error monitoring activity: " + e.getMessage());
        }
    }

    public void registerPerformance(String issueKey, String performanceData) {
        try {
            Issue issue = jira.getIssue(issueKey);
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: " + issueKey);
            }
            CustomField performanceField = customFieldManager.getCustomFieldByName("Performance");
            if (performanceField == null) {
                throw new IllegalArgumentException("Performance field not found");
            }
            TextField textField = (TextField) performanceField.getFieldObject();
            textField.setValue(issue, performanceData);
        } catch (Exception e) {
            System.err.println("Error registering performance: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        // Configuração do Jira
        Jira jira = new Jira(); // Implemente a configuração correta do Jira

        // Configuração dos campos personalizados
        FieldManager fieldManager = new FieldManager(); // Implemente a configuração correta dos campos personalizados
        CustomFieldManager customFieldManager = new CustomFieldManager(); // Implemente a configuração correta dos campos personalizados

        JavaAgent javaAgent = new JavaAgent(jira, fieldManager, customFieldManager);

        // Exemplos de uso das funções
        javaAgent.registerEvent("ABC-123", "Task Completed", "Completed the task");
        javaAgent.monitorActivity("ABC-123", "User Activity", "John Doe logged in");
        javaAgent.registerPerformance("ABC-123", "High CPU Usage Detected");
    }
}