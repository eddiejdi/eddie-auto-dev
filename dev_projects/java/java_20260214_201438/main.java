import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResults;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JiraService {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    public void trackActivity(String issueKey, String activity) {
        try (JiraClient client = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build()) {

            SearchResults searchResults = client.searchService().search("issue:" + issueKey);
            if (!searchResults.getIssues().isEmpty()) {
                Issue issue = searchResults.getIssues().get(0);
                client.issueService().update(issue.getId(), update -> update.setDescription(activity));
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    private static class Update {
        private String description;

        public Update(String description) {
            this.description = description;
        }

        public String getDescription() {
            return description;
        }

        public void setDescription(String description) {
            this.description = description;
        }
    }
}