import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.select.SelectField;
import com.atlassian.jira.issue.fields.select.Option;

public class JavaAgentJiraIntegrator {

    private Jira jira;
    private Project project;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;

    public JavaAgentJiraIntegrator(Jira jira, Project project, FieldManager fieldManager, CustomFieldManager customFieldManager) {
        this.jira = jira;
        this.project = project;
        this.fieldManager = fieldManager;
        this.customFieldManager = customFieldManager;
    }

    public void registerEvent(String eventDescription) {
        try {
            TextField textField = (TextField) customFieldManager.getCustomFieldByName("Event Description");
            Issue issue = jira.createIssue(project, "Event", textField.getValue(eventDescription));
            System.out.println("Event registered: " + issue.getKey());
        } catch (Exception e) {
            System.err.println("Error registering event: " + e.getMessage());
        }
    }

    public void monitorActivity(String activityDescription) {
        try {
            TextField textField = (TextField) customFieldManager.getCustomFieldByName("Activity Description");
            Issue issue = jira.createIssue(project, "Activity", textField.getValue(activityDescription));
            System.out.println("Activity registered: " + issue.getKey());
        } catch (Exception e) {
            System.err.println("Error monitoring activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        Jira jira = new Jira();
        Project project = jira.getProjectByKey("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        JavaAgentJiraIntegrator integrator = new JavaAgentJiraIntegrator(jira, project, fieldManager, customFieldManager);

        integrator.registerEvent("New feature implemented");
        integrator.monitorActivity("User interface updated");

        if (args.length > 0) {
            String eventDescription = args[0];
            integrator.registerEvent(eventDescription);
        }
    }
}