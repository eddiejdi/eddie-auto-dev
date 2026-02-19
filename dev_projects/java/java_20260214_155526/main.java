import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthHandler;
import com.atlassian.jira.client.jql.JqlQueryBuilder;
import com.atlassian.jira.client.jql.query.QueryResult;
import com.atlassian.jira.client.util.RestException;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClient(new BasicHttpAuthHandler(JIRA_URL, USERNAME, PASSWORD))) {

            // Example query to get all issues
            JqlQueryBuilder builder = JqlQueryBuilder.newBuilder();
            QueryResult result = client.searchIssues(builder.build());

            for (com.atlassian.jira.client.api.model.Issue issue : result.getIssues()) {
                System.out.println("Issue ID: " + issue.getKey());
                System.out.println("Summary: " + issue.getSummary());
                // Add more fields as needed
            }
        } catch (RestException e) {
            e.printStackTrace();
        }
    }
}