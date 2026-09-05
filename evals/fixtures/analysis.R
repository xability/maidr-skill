# Fuel-economy analysis for the quarterly report (rendered later from report.Rmd)
library(ggplot2)
library(dplyr)

cars <- mtcars |>
  mutate(cyl = factor(cyl, levels = c(4, 6, 8)))

summary_stats <- cars |>
  group_by(cyl) |>
  summarise(mean_mpg = mean(mpg), mean_wt = mean(wt), n = n(), .groups = "drop")
print(summary_stats)

p <- ggplot(cars, aes(x = wt, y = mpg, colour = cyl)) +
  geom_point(size = 3, alpha = 0.85) +
  labs(
    title = "Fuel economy versus weight",
    x = "Weight (1000 lbs)",
    y = "Miles per gallon",
    colour = "Cylinders"
  ) +
  theme_minimal()

p
