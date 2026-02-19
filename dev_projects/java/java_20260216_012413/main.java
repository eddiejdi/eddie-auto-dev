import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JiraIntegrationService {

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private ProjectManager projectManager;

    public void trackActivity(String issueKey, String activityDescription) {
        try {
            // Get the issue by key
            Issue issue = issueManager.getIssue(issueKey);

            // Check if the issue exists
            if (issue != null) {
                // Create a new comment in the issue
                issue.addComment(activityDescription);
                System.out.println("Activity tracked successfully for issue: " + issue.getKey());
            } else {
                System.out.println("Issue not found with key: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity for issue: " + issueKey);
            e.printStackTrace();
        }
    }

    public void trackProjectActivity(String projectId, String activityDescription) {
        try {
            // Get the project by ID
            Project project = projectManager.getProject(projectId);

            // Check if the project exists
            if (project != null) {
                // Create a new comment in the project
                issue.addComment(activityDescription);
                System.out.println("Activity tracked successfully for project: " + project.getKey());
            } else {
                System.out.println("Project not found with ID: " + projectId);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity for project: " + projectId);
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JiraIntegrationService service = new JiraIntegrationService();

        // Example usage
        service.trackActivity("ABC-123", "User logged in successfully");
        service.trackProjectActivity("JIRA-456", "New feature implemented");
    }
}