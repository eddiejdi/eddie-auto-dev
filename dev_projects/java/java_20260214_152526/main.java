import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceException;

public class JavaAgent {

    private Jira jira;

    public JavaAgent(Jira jira) {
        this.jira = jira;
    }

    public void trackActivity(String issueKey, String activityDescription) throws ServiceException {
        Issue issue = jira.getIssue(issueKey);
        if (issue == null) {
            throw new ServiceException("Issue not found: " + issueKey);
        }
        // Implement logic to log the activity in Jira
        System.out.println("Tracking activity for issue " + issueKey + ": " + activityDescription);
    }

    public static void main(String[] args) {
        try {
            Jira jira = new Jira(); // Initialize Jira service context
            JavaAgent javaAgent = new JavaAgent(jira);

            String issueKey = "ABC-123";
            String activityDescription = "User logged in";

            javaAgent.trackActivity(issueKey, activityDescription);
        } catch (ServiceException e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }
}