require 'json'

package = JSON.parse(File.read(File.join(__dir__, '..', 'package.json')))

Pod::Spec.new do |s|
  s.name           = 'BleSurvey'
  s.version        = package['version']
  s.summary        = package['description']
  s.description    = package['description']
  s.license        = { :type => 'MIT' }
  s.author         = 'IT Building Indoor Positioning'
  s.homepage       = 'https://example.invalid/it-building-indoor-positioning'
  s.platforms      = { :ios => '16.4' }
  s.swift_version  = '5.9'
  s.source         = { :git => 'https://example.invalid/it-building-indoor-positioning.git' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'
  s.source_files = '**/*.{h,m,mm,swift}'
end
