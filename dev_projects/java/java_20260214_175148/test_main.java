import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.ExtensionPoint;

import java.util.List;

@ComponentScan("com.example")
@ExtensionPoint
public class JiraAgent {

    private final Jira jira;
    private final FieldManager fieldManager;
    private final CustomFieldManager customFieldManager;
    private final ProjectManager projectManager;

    public JiraAgent(Jira jira, FieldManager fieldManager, CustomFieldManager customFieldManager, ProjectManager projectManager) {
        this.jira = jira;
        this.fieldManager = fieldManager;
        this.customFieldManager = customFieldManager;
        this.projectManager = projectManager;
    }

    public void trackActivity(String issueKey, String activityDescription) {
        try {
            Issue issue = jira.getIssue(issueKey);
            if (issue != null) {
                TextField summaryField = fieldManager.getFieldByName("Summary");
                TextField descriptionField = fieldManager.getFieldByName("Description");

                if (summaryField != null && descriptionField != null) {
                    issue.update(summaryField, activityDescription);
                    issue.update(descriptionField, activityDescription);

                    System.out.println("Activity tracked for issue " + issueKey);
                } else {
                    System.out.println("Summary or Description field not found");
                }
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity for issue " + issueKey + ": " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        Jira jira = new Jira(); // Implement the Jira service context
        FieldManager fieldManager = new FieldManager(); // Implement the FieldManager
        CustomFieldManager customFieldManager = new CustomFieldManager(); // Implement the CustomFieldManager
        ProjectManager projectManager = new ProjectManager(); // Implement the ProjectManager

        JiraAgent agent = new JiraAgent(jira, fieldManager, customFieldManager, projectManager);

        String issueKey = "ABC-123";
        String activityDescription = "Updated by Java Agent";

        agent.trackActivity(issueKey, activityDescription);
    }
}