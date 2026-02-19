import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;

@ComponentScan(basePackages = "com.example")
public class JavaAgentIntegration {

    public static void main(String[] args) {
        try {
            // Initialize Jira service context
            JiraServiceContext jiraServiceContext = new JiraServiceContext();

            // Get issue manager and project manager
            IssueManager issueManager = jiraServiceContext.getIssueManager();
            ProjectManager projectManager = jiraServiceContext.getProjectManager();

            // Example: Create a new issue
            String projectId = "PROJECT-123";
            String issueTypeKey = "TASK";
            String summary = "New task created by Java Agent Integration";

            Issue issue = issueManager.createIssue(projectId, issueTypeKey, summary);
            System.out.println("Created issue ID: " + issue.getId());

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}