import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResult;
import com.atlassian.jira.client.api.domain.User;
import com.atlassian.jira.client.api.service.IssueService;
import com.atlassian.jira.client.api.service.UserService;

import java.io.IOException;
import java.util.List;

public class JiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            UserService userService = client.getService(UserService.class);
            User user = userService.getUserByName("your-user-name");

            IssueService issueService = client.getService(IssueService.class);

            String projectKey = "YOUR-PROJECT-KEY";
            String issueType = "YOUR-ISSUE-TYPE";

            List<Issue> issues = issueService.searchByJql(projectKey + " AND type = " + issueType, null);
            for (Issue issue : issues) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getSummary());
                System.out.println("Status: " + issue.getStatus().getName());
                System.out.println("------------------------");
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}