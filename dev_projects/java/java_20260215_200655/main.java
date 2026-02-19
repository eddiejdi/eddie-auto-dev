import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraAuthenticationContext;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.security.JiraSecurityException;
import com.atlassian.jira.service.ServiceContextFactory;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;

public class JavaAgent {

    private Jira jira;
    private DataSource dataSource;

    public JavaAgent(Jira jira, DataSource dataSource) {
        this.jira = jira;
        this.dataSource = dataSource;
    }

    public void log(String message) throws JiraSecurityException {
        JiraAuthenticationContext authenticationContext = ServiceContextFactory.getJiraServiceContext();
        jira.log(authenticationContext, "Java Agent", message);
    }

    public void notify(String subject, String message) throws JiraSecurityException {
        JiraAuthenticationContext authenticationContext = ServiceContextFactory.getJiraServiceContext();
        jira.notify(authenticationContext, "Java Agent", subject, message);
    }

    public void monitorPerformance() throws SQLException {
        Connection connection = dataSource.getConnection();
        try (PreparedStatement preparedStatement = connection.prepareStatement("SELECT * FROM performance_data")) {
            ResultSet resultSet = preparedStatement.executeQuery();
            while (resultSet.next()) {
                String activity = resultSet.getString("activity");
                int duration = resultSet.getInt("duration");
                log("Activity: " + activity + ", Duration: " + duration);
            }
        } finally {
            connection.close();
        }
    }

    public void registerActivity(String activity) throws SQLException {
        Connection connection = dataSource.getConnection();
        try (PreparedStatement preparedStatement = connection.prepareStatement("INSERT INTO performance_data (activity, duration) VALUES (?, ?)")) {
            preparedStatement.setString(1, activity);
            preparedStatement.setInt(2, 0); // Assume duration is 0 for now
            preparedStatement.executeUpdate();
        } finally {
            connection.close();
        }
    }

    public static void main(String[] args) throws JiraSecurityException, SQLException {
        Jira jira = new Jira(); // Implement this with your actual Jira instance
        DataSource dataSource = new DataSource(); // Implement this with your actual database connection

        JavaAgent javaAgent = new JavaAgent(jira, dataSource);

        javaAgent.log("Java Agent started");
        javaAgent.monitorPerformance();
        javaAgent.registerActivity("Example Activity");

        javaAgent.notify("Performance Monitor", "Activity: Example Activity, Duration: 100ms");
    }
}