import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.user.UserManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class JavaAgent {

    private static final Logger logger = LoggerFactory.getLogger(JavaAgent.class);
    private IssueManager issueManager;
    private ProjectManager projectManager;
    private UserManager userManager;

    public JavaAgent() {
        this.issueManager = ComponentAccessor.getIssueManager();
        this.projectManager = ComponentAccessor.getProjectManager();
        this.userManager = ComponentAccessor.getUserManager();
    }

    public void trackActivity(String activity) {
        try {
            // Get the current user
            User currentUser = userManager.getUserByName("username");
            if (currentUser == null) {
                logger.error("User not found: username");
                return;
            }

            // Create a new issue or update an existing one
            Issue issue = issueManager.createIssue(currentUser, "Activity Tracking", activity);
            if (issue != null) {
                logger.info("Activity tracked successfully: {}", issue.getKey());
            } else {
                logger.error("Failed to track activity");
            }
        } catch (Exception e) {
            logger.error("Error tracking activity", e);
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.trackActivity("This is a test activity using Java Agent with Jira.");
    }
}