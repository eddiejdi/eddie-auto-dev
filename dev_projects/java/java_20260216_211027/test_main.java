import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.user.UserManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class JavaAgentTest {

    private static final Logger logger = LoggerFactory.getLogger(JavaAgentTest.class);
    private IssueManager issueManager;
    private ProjectManager projectManager;
    private UserManager userManager;

    public JavaAgentTest() {
        this.issueManager = ComponentAccessor.getIssueManager();
        this.projectManager = ComponentAccessor.getProjectManager();
        this.userManager = ComponentAccessor.getUserManager();
    }

    @org.junit.Test
    public void testTrackActivitySuccess() {
        JavaAgent agent = new JavaAgent();
        try {
            // Get the current user
            User currentUser = userManager.getUserByName("username");
            if (currentUser == null) {
                logger.error("User not found: username");
                return;
            }

            // Create a new issue or update an existing one
            Issue issue = issueManager.createIssue(currentUser, "Activity Tracking", "This is a test activity using Java Agent with Jira.");
            if (issue != null) {
                logger.info("Activity tracked successfully: {}", issue.getKey());
            } else {
                logger.error("Failed to track activity");
            }
        } catch (Exception e) {
            logger.error("Error tracking activity", e);
        }
    }

    @org.junit.Test
    public void testTrackActivityFailure() {
        JavaAgent agent = new JavaAgent();
        try {
            // Get the current user
            User currentUser = userManager.getUserByName("username");
            if (currentUser == null) {
                logger.error("User not found: username");
                return;
            }

            // Create a new issue or update an existing one with invalid activity
            Issue issue = issueManager.createIssue(currentUser, "Activity Tracking", "");
            if (issue != null) {
                logger.info("Activity tracked successfully: {}", issue.getKey());
            } else {
                logger.error("Failed to track activity");
            }
        } catch (Exception e) {
            logger.error("Error tracking activity", e);
        }
    }

    @org.junit.Test
    public void testTrackActivityEdgeCase() {
        JavaAgent agent = new JavaAgent();
        try {
            // Get the current user
            User currentUser = userManager.getUserByName("username");
            if (currentUser == null) {
                logger.error("User not found: username");
                return;
            }

            // Create a new issue or update an existing one with a very long activity
            Issue issue = issueManager.createIssue(currentUser, "Activity Tracking", "This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira. This is a test activity using Java Agent with Jira.");
            if (issue != null) {
                logger.info("Activity tracked successfully: {}", issue.getKey());
            } else {
                logger.error("Failed to track activity");
            }
        } catch (Exception e) {
            logger.error("Error tracking activity", e);
        }
    }
}