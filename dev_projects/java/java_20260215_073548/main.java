import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.user.UserManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JavaAgent {

    @Autowired
    private Jira jira;

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private CustomFieldManager customFieldManager;

    @Autowired
    private UserManager userManager;

    public void createIssue(String summary, String description) {
        try {
            ProjectManager projectManager = ComponentAccessor.getProjectManager();
            IssueManager issueManager = ComponentAccessor.getIssueManager();

            // Create a new issue
            com.atlassian.jira.issue.Issue issue = issueManager.createIssue(projectManager.getDefaultProject(), "Java Agent", summary);
            issue.setDescription(description);

            // Add custom fields if needed
            TextField customField = (TextField) customFieldManager.getFieldObjectByName("Custom Field Name");
            if (customField != null) {
                issue.addCustomFieldValue(customField, "Value for Custom Field");
            }

            // Save the issue
            issueManager.updateIssue(issue);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void monitorPerformance() {
        try {
            ProjectManager projectManager = ComponentAccessor.getProjectManager();
            IssueManager issueManager = ComponentAccessor.getIssueManager();

            // Create a new issue for performance monitoring
            com.atlassian.jira.issue.Issue issue = issueManager.createIssue(projectManager.getDefaultProject(), "Java Agent Performance Monitor", "Monitoring system performance");

            // Add custom fields if needed
            TextField customField = (TextField) customFieldManager.getFieldObjectByName("Custom Field Name");
            if (customField != null) {
                issue.addCustomFieldValue(customField, "Performance data for the last 24 hours");
            }

            // Save the issue
            issueManager.updateIssue(issue);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();

        // Example usage of createIssue method
        agent.createIssue("Java Agent Integration", "Integrating Java Agent with Jira for tracking activities.");

        // Example usage of monitorPerformance method
        agent.monitorPerformance();
    }
}