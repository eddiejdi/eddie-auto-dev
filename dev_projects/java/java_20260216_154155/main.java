import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.client.domain.Issue;
import com.atlassian.jira.client.service.IssueService;

public class JavaAgent {

    private JiraClient jiraClient;

    public JavaAgent(String username, String password) {
        BasicHttpAuthenticationHandler authHandler = new BasicHttpAuthenticationHandler(username, password);
        this.jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", authHandler);
    }

    public void createIssue(String issueKey, String summary, String description) throws Exception {
        IssueService issueService = jiraClient.getIssueService();
        Issue issue = issueService.create(issueKey, summary, description);
        System.out.println("Issue created: " + issue.getKey());
    }

    public void updateIssue(String issueKey, String summary, String description) throws Exception {
        IssueService issueService = jiraClient.getIssueService();
        Issue updatedIssue = issueService.update(issueKey, summary, description);
        System.out.println("Issue updated: " + updatedIssue.getKey());
    }

    public void deleteIssue(String issueKey) throws Exception {
        IssueService issueService = jiraClient.getIssueService();
        issueService.delete(issueKey);
        System.out.println("Issue deleted: " + issueKey);
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent("your-username", "your-password");

        try {
            agent.createIssue("TEST-123", "Test Issue", "This is a test issue.");
            agent.updateIssue("TEST-123", "Updated Test Issue", "This is an updated test issue.");
            agent.deleteIssue("TEST-123");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}