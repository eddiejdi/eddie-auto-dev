import com.atlassian.jira.rest.client.api.RestClient;
import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.api.domain.Issue;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthHandler;

public class JavaAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        RestClient restClient = new RestClientBuilder()
                .setEndpoint(JIRA_URL)
                .addAuthHandler(new BasicHttpAuthHandler(USERNAME, PASSWORD))
                .build();

        try {
            Issue issue = restClient.getIssue("YOUR-ISSUE-ID");
            System.out.println("Issue Title: " + issue.getKey() + ", Summary: " + issue.getSummary());
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}